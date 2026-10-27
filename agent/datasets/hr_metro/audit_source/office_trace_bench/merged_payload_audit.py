"""Narrow, source-bound external audit of non-anchor merged-cell cleanup.

Historical industry/legacy verifiers are left unchanged. A failed raw data
check can be adapted only after all missing stored values have been inspected,
including values beyond the historical check's twelve-example display cap.
"""
import posixpath
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from .contracts import sha256

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL_ID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
MERGED_CLEANUP_POLICIES = {
    ('egrid', '895cd81dd8662406189ad8adf5a2578dcb362cdb5cff7cca81b10ee6bd2447c6'):
        ('Contents',),
}


def _sheets(package):
    tree = ET.fromstring(package.read('xl/workbook.xml'))
    rels = {r.get('Id'): r.get('Target') for r in ET.fromstring(
        package.read('xl/_rels/workbook.xml.rels'))}
    result = {}
    for sheet in tree.find('{' + NS + '}sheets'):
        target = rels[sheet.get(REL_ID)]
        result[sheet.get('name')] = (target.lstrip('/') if target.startswith('/')
                                   else posixpath.normpath('xl/' + target))
    return tree, result


def _strings(package):
    if 'xl/sharedStrings.xml' not in package.namelist():
        return []
    tag = '{' + NS + '}t'
    return [''.join(t.text or '' for t in item.iter(tag)) for item in
            ET.fromstring(package.read('xl/sharedStrings.xml'))]


def _sheet(package, part, strings):
    tree = ET.fromstring(package.read(part))
    values = {}
    for cell in tree.iter('{' + NS + '}c'):
        formula = cell.find('{' + NS + '}f')
        if formula is not None:
            values[cell.get('r')] = ('formula', '=' + (formula.text or ''))
            continue
        value = cell.find('{' + NS + '}v')
        value = value.text if value is not None else None
        kind = cell.get('t', 'n')
        if kind == 's' and value is not None:
            value = strings[int(value)]
        elif kind == 'inlineStr':
            inline = cell.find('{' + NS + '}is')
            value = (None if inline is None else ''.join(
                t.text or '' for t in inline.iter('{' + NS + '}t')))
        elif kind == 'n' and value is not None:
            value = float(value) if any(s in value.lower() for s in ('.', 'e')) else int(value)
        elif kind == 'b' and value is not None:
            value = value == '1'
        if value is not None:
            values[cell.get('r')] = ('literal', value)
    return values, {m.get('ref') for m in tree.iter('{' + NS + '}mergeCell')}


def _same(old, new):
    from .industry_verification.workbooks import logical_value, normalized_formula
    from .industry_verification.verify import preserved_value
    if old is None or new is None:
        return old == new
    if old[0] != new[0]:
        return False
    if old[0] == 'formula':
        return normalized_formula(old[1]) == normalized_formula(new[1])
    return preserved_value(new[1], logical_value(old[1]))


def _source_references(package, tree, sheet_parts, candidates, reference_contains):
    """Do not forgive a value that is also used by a source formula/name."""
    from openpyxl.formula import Tokenizer
    bad = []

    def inspect(formula, current, location):
        tokens = Tokenizer(formula).items
        dynamic = any(t.type == 'FUNC' and t.subtype == 'OPEN' and
                      t.value[:-1].upper().removeprefix('_XLFN.') in ('INDIRECT', 'OFFSET')
                      for t in tokens)
        if dynamic or any(reference_contains(formula, sheet, cell, current)
                          for sheet, cell in candidates):
            if len(bad) < 12:
                bad.append(location)

    for sheet, part in sheet_parts.items():
        with package.open(part) as stream:
            for _, node in ET.iterparse(stream, events=('end',)):
                if node.tag == '{' + NS + '}f':
                    inspect('=' + (node.text or ''), sheet, 'formula:' + sheet)
                elif node.tag == '{' + NS + '}row':
                    node.clear()
    ignored = {'_xlnm.Print_Area', '_xlnm.Print_Titles', '_xlnm._FilterDatabase'}
    for item in tree.findall('{' + NS + '}definedNames/{' + NS + '}definedName'):
        if item.get('name') in ignored:
            continue
        scope = item.get('localSheetId')
        current = list(sheet_parts)[int(scope)] if scope is not None else ''
        inspect('=' + (item.text or '').lstrip('='), current, 'name:' + item.get('name', ''))
    return bad


def merged_cleanup_policy(manifest, workspace, reference_contains):
    """Return proofs for configured sheets only; never write a workbook."""
    digest = manifest['input_files'].get('input/' + manifest['workbook'])
    sheets = MERGED_CLEANUP_POLICIES.get((manifest['dataset_id'], digest))
    if not sheets:
        return None
    source = Path(workspace) / 'input' / manifest['workbook']
    output = Path(workspace) / 'output' / manifest['output_workbook']
    if sha256(source) != digest:
        raise ValueError('merged cleanup policy input hash mismatch')
    from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries, get_column_letter
    proofs, candidates = {}, []
    with ZipFile(source) as a, ZipFile(output) as b:
        tree, source_parts = _sheets(a)
        _, output_parts = _sheets(b)
        source_strings, output_strings = _strings(a), _strings(b)
        for sheet in sheets:
            old, merges = _sheet(a, source_parts[sheet], source_strings)
            new, output_merges = _sheet(b, output_parts[sheet], output_strings)
            allowed, forbidden, anchors = [], [], []
            bounds = [(area, range_boundaries(area)) for area in merges]
            for area, (c1, r1, _, _) in bounds:
                anchor = get_column_letter(c1) + str(r1)
                if not _same(old.get(anchor), new.get(anchor)):
                    anchors.append(anchor)
            for cell, value in old.items():
                if cell in new:
                    continue
                row, col = coordinate_to_tuple(cell)
                owners = [area for area, (c1, r1, c2, r2) in bounds
                          if c1 <= col <= c2 and r1 <= row <= r2 and (col, row) != (c1, r1)]
                if value[0] == 'literal' and len(owners) == 1 and owners[0] in output_merges:
                    allowed.append(cell)
                    candidates.append((sheet, cell))
                else:
                    forbidden.append(cell)
            proofs[sheet] = {'ok': merges == output_merges and not anchors and not forbidden,
                'merged_ranges_unchanged': merges == output_merges,
                'changed_anchors': anchors[:24], 'forbidden_missing': forbidden[:24],
                'normalized_missing': allowed, 'normalized_missing_count': len(allowed)}
        references = _source_references(a, tree, source_parts, candidates, reference_contains) if candidates else []
        for proof in proofs.values():
            proof['source_formula_or_name_references'] = references
            proof['ok'] = proof['ok'] and not references
    return {'version': 'egrid-merged-non-anchor-cleanup-v1', 'source_sha256': digest,
            'agent_manifest_modified': False, 'sheets': proofs}


def normalize_source_check(policy, name, ok, detail):
    """Keep additions/changed values/unknown losses as strict failures."""
    if ok or not policy or not name.startswith('source:data:') or not isinstance(detail, dict):
        return ok, detail
    sheet = name[len('source:data:'):]
    proof = policy['sheets'].get(sheet)
    if (not proof or not proof['ok'] or detail.get('changed') or detail.get('added')
            or not detail.get('missing') or not set(detail['missing']).issubset(proof['normalized_missing'])):
        return ok, detail
    return True, {'effective_content_preserved': True, 'strict_raw_observation': detail,
                  'normalization': policy['version'],
                  'normalized_missing_count': proof['normalized_missing_count']}
