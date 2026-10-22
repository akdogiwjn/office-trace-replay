"""spreadsheet-semantic-v3: layout-independent semantic checks with diagnostics.

The original-content comparison classifies damage from serialization noise:

  FAIL (strict, business meaning):
    source:worksheets / relative order, source:data (missing, changed or added
    real values), source:formulas (formula cells must stay formulas and only the
    explicitly supported serialization equivalences are accepted), source:charts,
    source:defined_names (a name is missing), source:defined_names_damaged (a
    name's target is invalid or broken, e.g. #REF!), source:merged_regions_removed
    (a source merge disappears), source:number_formats_meaning (a change that
    alters the unit expression).

  DIAGNOSTIC (recorded, not failing):
    empty-string cells normalized to empty cells on sheets declared by the
    manifest's empty_strings_policy, number-format serialization that keeps the
    unit expression, font/fill/alignment/border/protection representation,
    merged-region additions, defined-name attribute-text serialization whose
    target remains valid.

No extra full-table scans are introduced; the existing passes over each original
sheet feed both the strict checks and the diagnostic statistics.
"""
import gc
import re
from copy import copy
from itertools import zip_longest
from functools import lru_cache

from .contracts import read_json, sha256
from .workbooks import chart_sources, normalized_formula


def conditional_formatting_region_count(sheets):
    """Count unique worksheet regions covered by at least one rule.

    The unit is an effective sqref region, not an XML/openpyxl formatting
    group. LibreOffice may serialize multiple regions with the same rule in
    one ``ConditionalFormatting`` group. Repeated regions count once, and an
    empty rule group contributes nothing. This inspects range metadata only;
    it never iterates the cells inside a range.
    """
    covered = set()
    for sheet in sheets:
        collection = sheet.conditional_formatting
        for group in collection:
            try:
                rules = collection[group]
            except (KeyError, TypeError):
                rules = getattr(group, 'cfRule', ())
            if not any(rule is not None and getattr(rule, 'type', None)
                       for rule in (rules or ())):
                continue
            sqref = getattr(group, 'sqref', None)
            ranges = getattr(sqref, 'ranges', ())
            for cell_range in ranges:
                coordinate = getattr(cell_range, 'coord', None)
                if coordinate:
                    covered.add((sheet.title, coordinate.upper()))
    return len(covered)


_FORMAT_PLACEHOLDERS = frozenset('0#?')
_FORMAT_DATE_LETTERS = frozenset('ymdhs')
_CURRENCY_SYMBOLS = frozenset('$€£¥₹₩₽₺₫₴₦₱¢¤')
_FORMAT_COLORS = frozenset((
    'black', 'blue', 'cyan', 'green', 'magenta', 'red', 'white', 'yellow',
))
def _split_format_sections(code):
    """Split sections without treating quoted/escaped semicolons as syntax."""
    sections, current = [], []
    quoted = False
    bracket = False
    i = 0
    while i < len(code):
        ch = code[i]
        if ch == '\\' and i + 1 < len(code):
            current.extend((ch, code[i + 1]))
            i += 2
            continue
        if ch == '"':
            if quoted and i + 1 < len(code) and code[i + 1] == '"':
                current.extend(('"', '"'))
                i += 2
                continue
            quoted = not quoted
        elif not quoted and ch == '[':
            bracket = True
        elif not quoted and ch == ']':
            bracket = False
        if ch == ';' and not quoted and not bracket:
            sections.append(''.join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    sections.append(''.join(current))
    return sections


def _bracket_token(content):
    """Return a semantic token or None for a known presentation-only marker."""
    folded = content.casefold()
    if folded in _FORMAT_COLORS or re.fullmatch(r'color\d+', folded):
        return None
    if folded in ('h', 'm', 's'):
        return ('elapsed', folded)
    # Locale/currency markers use [$<currency>-<locale>]. Keep the currency
    # symbol in the meaning key, but locale identifiers are serialization
    # metadata and do not replace or erase the symbol.
    if content.startswith('$'):
        body = content[1:]
        currency, sep, locale = body.rpartition('-')
        if sep and re.fullmatch(r'(?:[0-9A-Fa-f]{3,8}|F[48]00)', locale):
            body = currency
        elif body.startswith('-') and re.fullmatch(r'-[0-9A-Fa-f]{3,8}', body):
            body = ''
        if body:
            return ('currency', body)
        return None
    # A locale-only marker has no explicit unit. Treat it as metadata, while
    # leaving all other bracket syntax opaque and therefore conservative.
    if re.fullmatch(r'-[0-9A-Fa-f]{3,8}', content):
        return None
    if re.fullmatch(r'(?:<=|>=|<>|=|<|>)[+-]?(?:\d+(?:\.\d*)?|\.\d+)', content):
        return ('condition', content.casefold())
    return ('unsupported-bracket', content)


def _numeric_token(segment):
    """Represent scaling separately from grouping; precision is presentation."""
    if segment.count('.') > 1:
        return None
    integer, dot, decimal = segment.partition('.')
    scale = len(integer) - len(integer.rstrip(','))
    integer = integer[:-scale] if scale else integer
    grouping = ',' in integer
    if any(ch not in _FORMAT_PLACEHOLDERS | {','} for ch in integer):
        return None
    if any(ch not in _FORMAT_PLACEHOLDERS for ch in decimal):
        return None
    # Group separators and decimal precision change presentation. Trailing
    # commas scale the value (thousands/millions) and are meaning-bearing.
    return ('number', bool(grouping), scale, bool(dot))


def _parse_format_section(section):
    """Tokenize the supported Excel format subset into semantic components."""
    raw_tokens = []
    i = 0
    while i < len(section):
        ch = section[i]
        if ch == '"':
            i += 1
            literal = []
            while i < len(section):
                if section[i] == '"':
                    if i + 1 < len(section) and section[i + 1] == '"':
                        literal.append('"')
                        i += 2
                        continue
                    i += 1
                    break
                literal.append(section[i])
                i += 1
            else:
                return None
            raw_tokens.append(('literal', ''.join(literal)))
            continue
        if ch == '\\':
            if i + 1 >= len(section):
                return None
            raw_tokens.append(('literal', section[i + 1]))
            i += 2
            continue
        if ch in '_*':  # spacing/fill controls do not carry a unit.
            if i + 1 >= len(section):
                return None
            i += 2
            continue
        if ch == '[':
            end = section.find(']', i + 1)
            if end < 0:
                return None
            token = _bracket_token(section[i + 1:end])
            if token:
                raw_tokens.append(token)
            i = end + 1
            continue
        upper_tail = section[i:].upper()
        if upper_tail.startswith('AM/PM'):
            raw_tokens.append(('field', 'ampm', 0))
            i += 5
            continue
        if upper_tail.startswith('A/P'):
            raw_tokens.append(('field', 'ampm_short', 0))
            i += 3
            continue
        if ch in '0#?,.':
            j = i + 1
            while j < len(section) and section[j] in '0#?,.':
                j += 1
            token = _numeric_token(section[i:j])
            if token is None:
                return None
            raw_tokens.append(token)
            i = j
            continue
        if ch.isalpha() and ch.casefold() in _FORMAT_DATE_LETTERS:
            j = i + 1
            while j < len(section) and section[j].casefold() == ch.casefold():
                j += 1
            raw_tokens.append(('raw-field', ch.casefold(), j - i))
            i = j
            continue
        if ch == '@':  # text placeholder, no unit meaning.
            i += 1
            continue
        if ch == '%':
            raw_tokens.append(('percent',))
            i += 1
            continue
        if ch in _CURRENCY_SYMBOLS:
            raw_tokens.append(('currency', ch))
            i += 1
            continue
        if ch.isalpha():
            # Scientific notation is common enough to retain explicitly.
            if ch.casefold() == 'e' and i + 1 < len(section) and section[i + 1] in '+-':
                j = i + 2
                while j < len(section) and section[j] in '0#?':
                    j += 1
                if j > i + 2:
                    raw_tokens.append(('exponent', section[i + 1], j - i - 2))
                    i = j
                    continue
            return None
        raw_tokens.append(('literal', ch))
        i += 1

    # Resolve m as month or minute using only adjacent time-field context.
    resolved = []
    for i, token in enumerate(raw_tokens):
        if token[0] != 'raw-field':
            resolved.append(token)
            continue
        _, letter, width = token
        if letter == 'm':
            minute = False
            for step in (-1, 1):
                j = i + step
                while 0 <= j < len(raw_tokens):
                    lo, hi = sorted((i, j))
                    middle = raw_tokens[lo + 1:hi]
                    if any(t != ('literal', ':') for t in middle):
                        break
                    other = raw_tokens[j]
                    if other[0] == 'raw-field':
                        if other[1] in ('h', 's'):
                            minute = True
                        break
                    j += step
            family = 'minute' if minute else 'month'
        else:
            family = {'y': 'year', 'd': 'day', 'h': 'hour', 's': 'second'}[letter]
        if family in ('year',):
            canonical_width = 4  # yy/y/yyyy serialization differences.
        elif family in ('month', 'day', 'hour', 'minute', 'second'):
            if width <= 2:
                canonical_width = 2  # optional zero padding.
            else:
                canonical_width = width  # weekday/month names stay distinct.
        else:
            canonical_width = width
        resolved.append(('field', family, canonical_width))
    merged = []
    for token in resolved:
        if token[0] == 'literal' and merged and merged[-1][0] == 'literal':
            merged[-1] = ('literal', merged[-1][1] + token[1])
        else:
            merged.append(token)
    # A quoted/escaped currency glyph remains a currency unit. Other literal
    # text stays case-sensitive and distinct from format-code operators.
    return tuple(('currency', token[1])
                 if token[0] == 'literal' and token[1] and
                 all(char in _CURRENCY_SYMBOLS for char in token[1]) else token
                 for token in merged)


@lru_cache(maxsize=512)
def _parse_format_cached(value):
    raw = '' if value is None else str(value)
    if raw.strip().casefold() in ('', 'general'):
        return (), True, 'general-equivalent'
    sections = _split_format_sections(raw)
    parsed = []
    for section in sections:
        tokens = _parse_format_section(section)
        if tokens is None:
            return ('unsupported-format', raw), False, 'unsupported-format-change-not-proven'
        parsed.append(tokens)
    return tuple(parsed), True, 'parsed-format-equivalence'


def format_meaning(value):
    """Return a cached semantic key for a conservative Excel format subset.

    Date field order, elapsed-time units, currency, percent, literal units and
    magnitude scaling are preserved. Zero padding, year width, code-letter
    case, locale identifiers, known colors and grouping commas are normalized.
    Opaque formats compare equal only when their raw codes are identical.
    """
    return _parse_format_cached(None if value is None else str(value))[0]


def compare_number_formats(source, output):
    """Classify one source/output pair without silently accepting opaque edits."""
    source_raw = '' if source is None else str(source)
    output_raw = '' if output is None else str(output)
    source_key, source_supported, _ = _parse_format_cached(source_raw)
    output_key, output_supported, _ = _parse_format_cached(output_raw)
    if source_key == output_key:
        return {'equivalent': True,
                'classification': 'unchanged' if source_raw == output_raw else 'allowed_representation_change',
                'reason': 'same_semantic_format_key', 'source_supported': source_supported,
                'output_supported': output_supported}
    if not source_supported or not output_supported:
        reason = 'unsupported_format_change_not_proven'
    else:
        reason = _format_difference_reason(source_key, output_key)
    return {'equivalent': False, 'classification': 'strict_failure', 'reason': reason,
            'source_supported': source_supported, 'output_supported': output_supported}


def _format_difference_reason(source_key, output_key):
    def flatten(key):
        if not isinstance(key, tuple):
            return []
        if key and isinstance(key[0], str) and key[0] == 'unsupported-format':
            return [key]
        result = []
        for item in key:
            if isinstance(item, tuple) and item and isinstance(item[0], tuple):
                result.extend(item)
            elif isinstance(item, tuple) and item and isinstance(item[0], str):
                result.append(item)
        return result

    source_tokens, output_tokens = flatten(source_key), flatten(output_key)
    source_text, output_text = repr(source_tokens), repr(output_tokens)
    if 'elapsed' in source_text or 'elapsed' in output_text:
        return 'elapsed_time_unit_or_field_changed'
    if 'currency' in source_text or 'currency' in output_text:
        return 'currency_unit_changed'
    if 'percent' in source_text or 'percent' in output_text:
        return 'percentage_unit_changed'
    if 'field' in source_text or 'field' in output_text:
        return 'date_time_fields_or_order_changed'
    if 'literal' in source_text or 'literal' in output_text:
        return 'literal_unit_changed'
    source_numbers = [t for t in source_tokens if t[0] == 'number']
    output_numbers = [t for t in output_tokens if t[0] == 'number']
    if source_numbers and output_numbers:
        if [t[2] for t in source_numbers] != [t[2] for t in output_numbers]:
            return 'numeric_scaling_changed'
        if [t[1] for t in source_numbers] != [t[1] for t in output_numbers]:
            return 'grouping_format_changed'
    return 'format_semantics_changed'


def _collect_names(book):
    """{(name, scope): DefinedName}; scope None=workbook-global or a sheet title."""
    names = {}
    for name, item in book.defined_names.items():
        names[(name, None)] = item
    for ws in book.worksheets:
        local = getattr(ws, 'defined_names', None)
        if not local:
            continue
        for name, item in local.items():
            names[(name, ws.title)] = item
    return names


_DN_SHEET_REF = re.compile(
    r"(?:'((?:[^']|'')+)'|([^!]+))!"
    r"(\$?[A-Z]{1,3}\$?\d+|\$?[A-Z]{1,3}|\$?[1-9]\d*)"
    r"(?::(\$?[A-Z]{1,3}\$?\d+|\$?[A-Z]{1,3}|\$?[1-9]\d*))?")
# Bare (no-sheet) target: a cell/row always has a digit; a column range has a
# colon. A single bare column letter is ambiguous with a name and is left to
# the name-reference branch.
_DN_BARE_RANGE = re.compile(
    r"\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?"
    r"|\$?[1-9]\d*(?::\$?[1-9]\d*)?"
    r"|\$?[A-Z]{1,3}:\$?[A-Z]{1,3}")
_DN_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
_DN_NUMBER = re.compile(r'^[+-]?(\d+(\.\d*)?|\.\d+)([Ee][+-]?\d+)?$')
_DN_STRING = re.compile(r'^"(?:[^"]|"")*"$')
_DN_BOOL = re.compile(r'^(TRUE|FALSE)$', re.I)
_BROKEN_TOKENS = ('#REF!', '#NAME?', '#VALUE!', '#DIV/0!', '#N/A', '#NULL!')


def _name_is_broken(item):
    return any(tok in str(getattr(item, 'attr_text', '')) for tok in _BROKEN_TOKENS)


def _normalize_range(r1, r2=None):
    first = r1.replace('$', '').upper()
    second = r2.replace('$', '').upper() if r2 else None
    return first + (':' + second if second else '')


def _resolve_referenced(name, scope, book, names, seen):
    """Resolve a defined-name reference, with cycle detection."""
    binding = _lookup_name(name, scope, names)
    if binding is None:
        return None  # referenced name does not exist
    found_key, target = binding
    if found_key in seen:
        return ('cycle', name)
    seen.add(found_key)
    return _resolve_name_meaning(target, book, names, found_key[1], seen)


def _resolve_name_meaning(item, book, names, scope, seen):
    """Canonical meaning of a defined-name target, or None if unresolvable."""
    text = str(getattr(item, 'attr_text', '')).strip()
    if text.startswith('='):
        text = text[1:]
    if any(tok in text for tok in _BROKEN_TOKENS):
        return ('broken', text)
    match = _DN_SHEET_REF.fullmatch(text)
    if match:
        sheet = match.group(1) or match.group(2)
        sheet = sheet.replace("''", "'")
        if sheet not in book:
            return None  # missing sheet
        return ('range', sheet, _normalize_range(match.group(3), match.group(4)))
    if _DN_BARE_RANGE.fullmatch(text):
        # relative range; resolved in the name's own scope
        return ('range', scope, _normalize_range(text))
    if _DN_NAME.fullmatch(text):
        return _resolve_referenced(text, scope, book, names, seen)
    if _DN_NUMBER.fullmatch(text):
        return ('const', 'number', format(float(text), '.12g'))
    if _DN_STRING.fullmatch(text):
        return ('const', 'string', text[1:-1].replace('""', '"'))
    if _DN_BOOL.fullmatch(text):
        return ('const', 'bool', text.upper())
    # function/complex expression: only an explicitly supported serialization
    # equivalence is accepted; anything changed is rejected.
    return ('expr', normalized_formula(text))


def _lookup_name(name, scope, names):
    """Excel names are case-insensitive; worksheet-local names take priority."""
    for wanted_scope in dict.fromkeys((scope, None)):
        for key, item in names.items():
            if key[1] == wanted_scope and key[0].casefold() == name.casefold():
                return key, item
    return None


def _shadowed_formula_names(formulas, source, output, src_names, out_names):
    """Reject additions that change name resolution in original formulas.

    Inspect RANGE operands, so string literals and function names do not count
    as name uses. Unused additions and equivalent bindings remain permitted.
    """
    from openpyxl.formula import Tokenizer
    from openpyxl.formula.tokenizer import TokenizerError

    source_keys = {(name.casefold(), scope) for name, scope in src_names}
    additions = {(name.casefold(), scope) for name, scope in out_names
                 if (name.casefold(), scope) not in source_keys}
    if not additions:
        return []
    changed = []
    for sheet, address, formula in formulas:
        try:
            tokens = Tokenizer(formula).items
        except TokenizerError:
            if any(scope in (None, sheet) for _, scope in additions):
                changed.append(f'{sheet}!{address}: cannot resolve formula names')
            continue
        for token in tokens:
            if token.type != 'OPERAND' or token.subtype != 'RANGE':
                continue
            scope, name = sheet, token.value
            if '!' in name:
                scope, name = name.rsplit('!', 1)
                if scope.startswith("'") and scope.endswith("'"):
                    scope = scope[1:-1].replace("''", "'")
            if not any((name.casefold(), s) in additions for s in (scope, None)):
                continue
            before = _lookup_name(name, scope, src_names)
            after = _lookup_name(name, scope, out_names)
            if before is None or after is None:
                changed.append(f'{sheet}!{address}: {token.value}')
                continue
            old_key, old_item = before
            new_key, new_item = after
            if old_key == new_key:
                continue  # Existing binding preservation is checked separately.
            old_meaning = _resolve_name_meaning(old_item, source, src_names, old_key[1], {old_key})
            new_meaning = _resolve_name_meaning(new_item, output, out_names, new_key[1], {new_key})
            if (old_meaning is None or new_meaning is None or old_meaning != new_meaning
                    or old_meaning[0] in ('expr', 'broken', 'cycle')):
                changed.append(f'{sheet}!{address}: {token.value}')
    return changed


def original_content(source, output, checks, empty_string_policy=None):
    """Compare each original occupied coordinate, not a global row/column template."""
    from openpyxl import load_workbook
    from .verify import preserved_value
    from .workbooks import logical_value
    allowed_empty = set()
    if isinstance(empty_string_policy, dict):
        allowed_empty = set(empty_string_policy.get('sheets', []))
    a = load_workbook(source, read_only=True, data_only=False)
    b = load_workbook(output, read_only=True, data_only=False)
    try:
        original_names = a.sheetnames
        checks.add('source:worksheets', all(n in b for n in original_names), b.sheetnames)
        checks.add('source:relative_order', [n for n in b.sheetnames if n in original_names] == original_names)
        for name in original_names:
            if name not in b:
                continue
            missing, changed, formulas, added = [], [], [], []
            empty_string, numfmt, unit_diffs = [], [], []
            number_format_pairs = {}
            number_format_difference_count = 0
            number_format_allowed_count = 0
            number_format_strict_count = 0
            number_format_samples = []
            for left, right in zip_longest(a[name].iter_rows(), b[name].iter_rows(), fillvalue=()):
                for old, new in zip_longest(left, right):
                    if old is None or old.value is None:
                        if new is not None and new.value not in (None, '') and len(added) < 12:
                            added.append(new.coordinate)
                        continue
                    address = old.coordinate
                    if new is None or new.value is None:
                        if old.value == '':
                            # Empty-string markers become empty cells after
                            # openpyxl/LibreOffice serialization. Only sheets
                            # declared by the manifest policy are eligible.
                            if name in allowed_empty:
                                if len(empty_string) < 24:
                                    empty_string.append(address)
                            elif len(missing) < 12:
                                missing.append(address)
                        elif len(missing) < 12:
                            missing.append(address)
                    elif old.value == '':
                        if new.value != '' and len(changed) < 12:
                            changed.append(address)
                    elif old.data_type == 'f':
                        # A formula must remain a formula cell with the same
                        # formula; only supported serialization equivalences are
                        # accepted and string literals are compared verbatim.
                        if new.data_type != 'f' or normalized_formula(old.value) != normalized_formula(new.value):
                            if len(formulas) < 12:
                                formulas.append(address)
                    elif not preserved_value(new.value, logical_value(old.value)) and len(changed) < 12:
                        changed.append(address)
                    if new is not None:
                        old_format = '' if old.number_format is None else str(old.number_format)
                        new_format = '' if new.number_format is None else str(new.number_format)
                        comparison = compare_number_formats(old_format, new_format)
                        if old_format != new_format:
                            number_format_difference_count += 1
                            classification = comparison['classification']
                            if classification == 'allowed_representation_change':
                                number_format_allowed_count += 1
                            else:
                                number_format_strict_count += 1
                            pair_key = (old_format, new_format, classification, comparison['reason'])
                            pair = number_format_pairs.setdefault(pair_key, {'count': 0, 'samples': []})
                            pair['count'] += 1
                            if len(pair['samples']) < 5:
                                pair['samples'].append(address)
                            if len(number_format_samples) < 24:
                                number_format_samples.append({
                                    'cell': address, 'source': old_format, 'output': new_format,
                                    'classification': classification, 'reason': comparison['reason'],
                                })
                        if not comparison['equivalent']:
                            if len(unit_diffs) < 24:
                                unit_diffs.append(address)
                        elif old_format != new_format:
                            if len(numfmt) < 24:
                                numfmt.append(address)
            checks.add('source:data:' + name, not missing and not changed and not added,
                       dict(missing=missing, changed=changed, added=added))
            checks.add('source:formulas:' + name, not formulas, formulas)
            checks.add('source:number_formats_meaning:' + name,
                       number_format_strict_count == 0, unit_diffs)
            checks.diag('source:number_formats:' + name, numfmt)
            checks.diag('source:empty_string_normalized:' + name, empty_string)
            checks.data.setdefault('number_format_statistics', {})[name] = {
                'difference_count': number_format_difference_count,
                'distinct_format_pair_count': len(number_format_pairs),
                'allowed_representation_change_count': number_format_allowed_count,
                'strict_failure_count': number_format_strict_count,
                'cell_sample_limit': 24,
                'cell_samples': number_format_samples,
                'format_pairs': [
                    {'source': key[0], 'output': key[1], 'classification': key[2],
                     'reason': key[3], 'count': value['count'],
                     'cell_samples': value['samples']}
                    for key, value in sorted(number_format_pairs.items())
                ],
            }
    finally:
        a.close(); b.close()
    # Non-cell structures are small; load originals one time to inspect their object graph.
    a = load_workbook(source, data_only=False)
    b = load_workbook(output, data_only=False)
    try:
        original_formulas = []
        for sheet in a:
            if sheet.title not in b:
                continue
            other = b[sheet.title]
            merged = {str(r) for r in sheet.merged_cells.ranges}
            merged_other = {str(r) for r in other.merged_cells.ranges}
            removed = sorted(merged - merged_other)
            added_merge = sorted(merged_other - merged)
            # Removed source merges are structure damage; additions are
            # representation noise (data checks guard any content loss).
            checks.add('source:merged_regions_removed:' + sheet.title, not removed, removed)
            checks.diag('source:merged_regions:' + sheet.title, added_merge)
            sources = [(type(c).__name__, chart_sources(c)) for c in other._charts]
            wanted = [(type(c).__name__, chart_sources(c)) for c in sheet._charts]
            checks.add('source:charts:' + sheet.title, len(sources) >= len(wanted) and all(sources.count(s) >= wanted.count(s) for s in wanted), sources)
            # Style identity uses semantic objects, never style IDs, which engines reorder.
            differences = []
            compared_styles = {}
            for cell in sheet._cells.values():
                if cell.data_type == 'f':
                    original_formulas.append((sheet.title, cell.coordinate, cell.value))
                new = other[cell.coordinate]
                # IDs are only a cache key scoped to these two books. Compare the
                # underlying objects once per pair, never IDs across workbooks.
                pair = (cell.style_id, new.style_id)
                if pair not in compared_styles:
                    compared_styles[pair] = [attr for attr in ('font', 'fill', 'alignment', 'border', 'protection')
                                             if copy(getattr(cell, attr)) != copy(getattr(new, attr))]
                for attr in compared_styles[pair]:
                    if len(differences) < 24:
                        differences.append(cell.coordinate + ':' + attr)
            checks.diag('source:styles:' + sheet.title, differences)
        missing_names, damaged_names, serialized_names, added_names = [], [], [], []
        src_names = _collect_names(a)
        out_names = _collect_names(b)
        for (name, scope) in src_names:
            label = f'{name}@{scope or "global"}'
            if (name, scope) not in out_names:
                missing_names.append(label)
                continue
            old_item = src_names[(name, scope)]
            new_item = out_names[(name, scope)]
            if _name_is_broken(old_item):
                # A name already broken in the source is only a historical
                # state when its content stays byte-identical.
                if str(old_item.attr_text) != str(new_item.attr_text):
                    damaged_names.append(label)
                continue
            old_meaning = _resolve_name_meaning(old_item, a, src_names, scope, set())
            new_meaning = _resolve_name_meaning(new_item, b, out_names, scope, set())
            if old_meaning is None or new_meaning is None or old_meaning != new_meaning:
                damaged_names.append(label)
            elif str(old_item.attr_text) != str(new_item.attr_text):
                serialized_names.append(label)
        for (name, scope) in out_names:
            if (name, scope) not in src_names:
                added_names.append(f'{name}@{scope or "global"}')
        checks.add('source:defined_names', not missing_names, missing_names)
        checks.add('source:defined_names_damaged', not damaged_names, damaged_names)
        shadowed = _shadowed_formula_names(original_formulas, a, b, src_names, out_names)
        checks.add('source:defined_name_shadowing', not shadowed, shadowed[:12])
        checks.diag('source:defined_names_serialization', serialized_names)
        checks.diag('source:defined_names_added', added_names)
    finally:
        a.close(); b.close(); del a, b; gc.collect()


REF = re.compile(r"(?:(?:'((?:[^']|'')+)'|([A-Za-z_][A-Za-z0-9_. ]*))!)?(\$?[A-Z]{1,3}\$?\d+)(?::(\$?[A-Z]{1,3}\$?\d+))?")


def dependencies(book, location, seen=None):
    """Transitive references, allowing any formula implementation and helper sheets."""
    from openpyxl.utils.cell import range_boundaries, get_column_letter
    seen = set() if seen is None else seen
    name, address = location
    key = (name, address.replace('$', ''))
    if key in seen:
        return seen
    seen.add(key)
    if name not in book:
        return seen
    cell = book[name][key[1]]
    if cell.data_type != 'f':
        return seen
    # Ignore literal strings (e.g. INDIRECT text is not accepted as proven dependency).
    formula = re.sub(r'"(?:[^"]|"")*"', '""', str(cell.value))
    for match in REF.finditer(formula):
        target = (match[1] or match[2] or name).replace("''", "'")
        start, end = match[3].replace('$', ''), (match[4] or match[3]).replace('$', '')
        lo, bottom, hi, top = range_boundaries(start + ':' + end)
        # Large source ranges establish a sheet dependency without enumerating millions of cells.
        if (hi - lo + 1) * (top - bottom + 1) > 5000:
            seen.add((target, '*')); continue
        for row in range(bottom, top + 1):
            for col in range(lo, hi + 1):
                dependencies(book, (target, get_column_letter(col) + str(row)), seen)
    return seen


def direct_formula_references(book, location):
    """Return only references written in this cell's formula.

    This is intentionally non-recursive and is used by the measured loop
    contract to confirm direct links without auditing the full dependency
    graph.  The independent acceptance verifier retains ``dependencies``.
    """
    name, address = location
    if name not in book:
        return set()
    cell = book[name][address.replace('$', '')]
    if cell.data_type != 'f':
        return set()
    formula = re.sub(r'"(?:""|[^"])*"', '""', str(cell.value))
    references = set()
    for match in REF.finditer(formula):
        target = (match[1] or match[2] or name).replace("''", "'")
        references.add((target, match[3].replace('$', ''),
                        (match[4] or match[3]).replace('$', '')))
    return references


def reference_covers_cell(reference, location):
    """Whether a direct A1 reference/range contains a worksheet cell."""
    from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries

    sheet, first, last = reference
    target_sheet, address = location
    if sheet != target_sheet:
        return False
    try:
        min_col, min_row, max_col, max_row = range_boundaries(
            first.replace('$', '') + ':' + last.replace('$', ''))
        row, col = coordinate_to_tuple(address.replace('$', ''))
    except (TypeError, ValueError):
        return False
    return min_row <= row <= max_row and min_col <= col <= max_col


def _sheet_scale_evidence(req, sheet_name, output_sheet):
    """Compare the same serialized/effective extent on both sides.

    New manifests may freeze richer evidence at preparation time.  The
    compatibility fallback keeps legacy manifests working, but new compiles
    should not use read-only ``max_row`` as a data extent: that value can be
    the worksheet's declared XML dimension, including an empty trailing row.
    """
    details = req.get('base_dimension_details', {}).get(sheet_name, {})
    effective = details.get('effective_data_range')
    if effective is None:
        effective = req['base_dimensions'][sheet_name]
    source = tuple(effective)
    target = ((output_sheet.max_row or 0), (output_sheet.max_column or 0)) if output_sheet else (0, 0)
    required_cells = details.get('boundary_cells', [])
    boundary_ok = bool(output_sheet) and all(output_sheet[address].value is not None
                                               for address in required_cells)
    return (bool(output_sheet) and target[0] >= source[0] and target[1] >= source[1]
            and boundary_ok), {
                'source_effective_data_range': source,
                'output_serialized_cell_range': target,
                'source_declared_dimension': details.get('declared_dimension'),
                'source_serialized_cell_range': details.get('serialized_cell_range'),
                'boundary_cells': required_cells,
                'boundary_cells_present': boundary_ok,
            }


def _scenario_formula_link(book, references, selector, assumptions):
    """Accept a direct scenario link or one explicit formula intermediate.

    This is a bounded loop structural check, not a transitive dependency walk.
    Full selector-to-source graph proof remains part of independent acceptance.
    """
    if any(reference_covers_cell(ref, selector) for ref in references):
        return True, 'direct_selector_reference'
    if any(reference_covers_cell(ref, location)
           for ref in references for location in assumptions):
        return True, 'direct_assumption_reference'
    for sheet, first, last in references:
        if first != last or sheet not in book:
            continue
        try:
            location = (sheet, first.replace('$', ''))
            if book[sheet][location[1]].data_type != 'f':
                continue
            # Expand exactly one formula cell and inspect only the references
            # written in it. Do not recurse through another formula or enumerate
            # cells in a referenced range.
            intermediate_refs = direct_formula_references(book, location)
            if any(reference_covers_cell(ref, selector) for ref in intermediate_refs):
                return True, 'single_formula_intermediate_to_selector'
            if any(reference_covers_cell(ref, assumption)
                   for ref in intermediate_refs for assumption in assumptions):
                return True, 'single_formula_intermediate_to_assumption'
        except (KeyError, ValueError):
            continue
    return False, 'no_direct_or_one_level_scenario_reference'


def _derived_sheet_specs(req):
    """Frozen derived-sheet declarations, only when a manifest makes them explicit."""
    specs = req.get('derived_sheets')
    return specs if isinstance(specs, dict) else {}


def _derived_metric_anchor(req, metric_id):
    for sheet, spec in _derived_sheet_specs(req).items():
        anchor = (spec.get('metric_anchors') or {}).get(metric_id)
        if anchor:
            return sheet, anchor.replace('$', '').upper()
    return None


def _derived_chart_series(req, chart_id):
    for sheet, spec in _derived_sheet_specs(req).items():
        series = (spec.get('chart_series') or {}).get(chart_id)
        if series:
            return sheet, series
    return None


def _same_area(actual, declared):
    def normalize(area):
        return str(area).replace('$', '').upper()
    return normalize(actual) == normalize(declared)


def _resolve_prepared_path(document, dotted):
    """Resolve a dotted path in the frozen preparation artifact.

    ``x[].field`` resolves to the list of ``field`` values over the list ``x``;
    every other segment is a plain mapping lookup.  Missing keys raise KeyError
    so the caller can fail the corresponding check.
    """
    value = document
    parts = dotted.split('.')
    index = 0
    while index < len(parts):
        part = parts[index]
        if part.endswith('[]'):
            key = part[:-2]
            if not isinstance(value, dict) or key not in value:
                raise KeyError(dotted)
            items = value[key]
            if not isinstance(items, list):
                raise KeyError(dotted)
            field = parts[index + 1] if index + 1 < len(parts) else None
            try:
                return [item[field] for item in items]
            except (TypeError, KeyError):
                raise KeyError(dotted)
        if not isinstance(value, dict) or part not in value:
            raise KeyError(dotted)
        value = value[part]
        index += 1
    return value


def _prepared_value_matches(actual, expected):
    """Compare a frozen-preparation value with a workbook/diagnostic value."""
    from .verify import same_number
    if isinstance(expected, bool) or isinstance(expected, str):
        return actual == expected
    if isinstance(expected, (int, float)):
        return same_number(actual, expected)
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            return False
        return all(_prepared_value_matches(actual[key], value)
                   for key, value in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        return all(_prepared_value_matches(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _category_cell_date(value):
    """Return a date for a category cell that holds a datetime, date or Excel serial."""
    from datetime import date, datetime
    from openpyxl.utils.datetime import from_excel
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 1 <= value <= 2958465:
        converted = from_excel(value)
        if isinstance(converted, datetime):
            return converted.date()
        if isinstance(converted, date):
            return converted
    return None


def _load_prepared_selection(req, workspace, checks, sheet, dataset_id=None):
    """Load and identity-check the frozen artifact backing a derived sheet.

    This reads one small JSON and compares identity fields; the original
    large workbook is never opened here.  ``dataset_id`` is checked only when
    provided (loop/independent callers pass the manifest's dataset_id).
    """
    from .contracts import read_json
    relative = _derived_sheet_specs(req)[sheet].get('prepared_selection')
    if not relative:
        return None
    path = workspace / relative
    try:
        artifact = read_json(path)
    except (OSError, ValueError) as exc:
        checks.add('derived:prepared_selection:' + sheet, False,
                   {'error': f'{type(exc).__name__}: {exc}', 'path': relative})
        return None
    problems = []
    if artifact.get('schema_version') != 'xlsx-prepared-selection-v1':
        problems.append(f"schema {artifact.get('schema_version')!r}")
    if dataset_id is not None and artifact.get('dataset_id') != dataset_id:
        problems.append(f"dataset {artifact.get('dataset_id')!r} != {dataset_id!r}")
    if artifact.get('workload_version') != 'manual-workflow-adaptation-v2':
        problems.append(f"workload version {artifact.get('workload_version')!r}")
    checks.add('derived:prepared_selection:' + sheet, not problems,
               {'schema_version': artifact.get('schema_version'),
                'dataset_id': artifact.get('dataset_id'),
                'workload_version': artifact.get('workload_version'),
                'input_sha256': artifact.get('input_sha256'),
                'path': relative, 'problems': problems})
    return artifact


def check_derived_sheets(req, expected, book, cache, checks, original_names,
                         workspace=None, dataset_id=None):
    """Structure and frozen-value checks for declared derived sheets.

    A derived sheet is a small, explicitly declared frozen-preparation
    artifact.  It must exist as an added sheet (never impersonating an
    official original worksheet), stay within its declared size bound, contain
    no formulas (which would reintroduce in-sheet recomputation over source
    ranges), and hold exactly the frozen values the independent oracle
    expects.  When the declaration binds the frozen preparation artifact, the
    full derived content is verified against it: KPI anchors, the twelve
    monthly dates and sales values, the chart category/value ranges, the
    preparation diagnostics cells and the delivered business-diagnostics JSON.
    Only the small JSON and the bounded derived ranges are read; the original
    worksheet is never rescanned.  Used by both the measured loop and
    independent acceptance.
    """
    from datetime import date
    from .verify import same_number
    specs = _derived_sheet_specs(req)
    for sheet, spec in specs.items():
        if sheet in original_names:
            # A derived sheet declared as an original worksheet is a
            # contradictory manifest and must never bypass the checks.
            checks.add('derived:sheet_present:' + sheet, False,
                       {'declared_as_original': True, 'original_names': list(original_names)})
            continue
        present = sheet in book.sheetnames
        checks.add('derived:sheet_present:' + sheet, present,
                   {'declared': sheet, 'original_names': list(original_names),
                    'actual': book.sheetnames})
        if not present:
            continue
        worksheet = book[sheet]
        limit = spec.get('max_rows', 40)
        checks.add('derived:sheet_size:' + sheet,
                   (worksheet.max_row or 0) <= limit,
                   {'max_row': worksheet.max_row, 'limit': limit})
        formulas = [cell.coordinate for row in worksheet.iter_rows()
                    for cell in row if cell.data_type == 'f']
        checks.add('derived:no_formulas:' + sheet, not formulas, formulas[:12])
        prepared = _load_prepared_selection(
            req, workspace, checks, sheet, dataset_id) \
            if (workspace is not None and spec.get('prepared_selection')) else None
        for metric_id, address in (spec.get('metric_anchors') or {}).items():
            wanted = (expected.get('metric_values') or {}).get(metric_id)
            actual = cache[sheet][address.replace('$', '')].value
            checks.add('derived:anchor_value:' + sheet + '!' + address,
                       wanted is not None and same_number(actual, wanted),
                       {'actual': actual, 'expected': wanted,
                        'metric': metric_id})
            source_path = (spec.get('metric_value_paths') or {}).get(metric_id)
            if prepared is not None and source_path:
                try:
                    frozen = _resolve_prepared_path(prepared, source_path)
                except KeyError:
                    frozen = None
                checks.add('derived:anchor_source_value:' + sheet + '!' + address,
                           frozen is not None and same_number(actual, frozen),
                           {'actual': actual, 'prepared_selection_value': frozen,
                            'path': source_path})
        for item in spec.get('frozen_cells') or ():
            address = item['address'].replace('$', '')
            actual = cache[sheet][address].value
            try:
                frozen = _resolve_prepared_path(prepared, item['path'])
            except KeyError:
                frozen = None
            checks.add('derived:frozen_cell:' + sheet + '!' + address,
                       prepared is not None and frozen is not None
                       and _prepared_value_matches(actual, frozen),
                       {'actual': actual, 'prepared_selection_value': frozen,
                        'path': item['path']})
        for chart_id, series_spec in (spec.get('chart_series') or {}).items():
            dates_spec = series_spec.get('category_dates')
            if not dates_spec:
                continue
            try:
                cells = [cell for row in book[sheet][series_spec['category_range']
                                                   .replace('$', '')]
                         for cell in row]
            except (KeyError, ValueError):
                checks.add('derived:chart_categories:' + sheet + ':' + chart_id,
                           False, {'error': 'category range is not readable',
                                   'range': series_spec.get('category_range')})
                continue
            start = date.fromisoformat(dates_spec['start'])
            months = int(dates_spec['months'])
            def month_offset(months_ahead):
                year = start.year + (start.month - 1 + months_ahead) // 12
                month = (start.month - 1 + months_ahead) % 12 + 1
                return date(year, month, 1)
            wanted_dates = [month_offset(offset) for offset in range(months)]
            actual_dates = [_category_cell_date(cell.value) for cell in cells]
            ok = (len(cells) == months
                  and all(value is not None for value in actual_dates)
                  and actual_dates == wanted_dates)
            checks.add('derived:chart_categories:' + sheet + ':' + chart_id, ok,
                       {'expected_first': str(wanted_dates[0]) if wanted_dates else None,
                        'expected_months': months,
                        'actual_dates': [str(value) if value else None
                                         for value in actual_dates[:months + 1]]})
            value_path = series_spec.get('value_path')
            if prepared is not None and value_path:
                try:
                    frozen_values = _resolve_prepared_path(prepared, value_path)
                except KeyError:
                    frozen_values = None
                value_range = series_spec['value_range'].replace('$', '')
                actual_values = [cache[sheet][cell.coordinate].value
                                 for row in book[sheet][value_range] for cell in row]
                ok = (frozen_values is not None and len(actual_values) == len(frozen_values)
                      and all(same_number(a, b)
                              for a, b in zip(actual_values, frozen_values)))
                checks.add('derived:chart_source_values:' + sheet + ':' + chart_id, ok,
                           {'actual': actual_values,
                            'prepared_selection_value': frozen_values})


def check_diagnostics_bindings(req, workspace, checks):
    """Verify delivered business-diagnostics JSON values against the frozen artifact."""
    from .contracts import read_json
    binding = req.get('diagnostics_bindings')
    if not isinstance(binding, dict) or not binding.get('keys'):
        return
    output = workspace / 'output' / binding.get('file', 'xlsx_business_diagnostics.json')
    try:
        diagnostics = read_json(output)
    except (OSError, ValueError) as exc:
        checks.add('derived:diagnostics:' + binding.get('file', ''), False,
                   {'error': f'{type(exc).__name__}: {exc}'})
        return
    relative = binding.get('prepared_selection')
    artifact = None
    if relative:
        try:
            artifact = read_json(workspace / relative)
        except (OSError, ValueError):
            artifact = None
    for key, source_path in binding['keys'].items():
        actual = diagnostics.get(key)
        try:
            frozen = _resolve_prepared_path(artifact, source_path) if artifact else None
        except KeyError:
            frozen = None
        checks.add('derived:diagnostics:' + key,
                   artifact is not None and frozen is not None
                   and _prepared_value_matches(actual, frozen),
                   {'actual': actual, 'prepared_selection_value': frozen,
                    'path': source_path})


def verify_semantic_xlsx(manifest, expected, workspace, checks, deferred_outputs=()):
    from openpyxl import load_workbook
    from .verify import same_number, color, ERRORS
    req = manifest['requirements']; output = workspace / 'output'
    path = output / manifest['output_workbook']
    checks.add('workbook_file', path.is_file())
    if not path.is_file():
        return
    source = workspace / 'input' / manifest['workbook']
    original_content(source, path, checks,
                     empty_string_policy=req.get('empty_strings_policy'))
    book = load_workbook(path, data_only=False)
    cache = load_workbook(path, data_only=True)
    src = load_workbook(source, read_only=True)
    originals = set(src.sheetnames); src.close()
    features = read_json(output / 'workbook_features.json')
    occupied = set()
    def locate(spec, formula=False):
        name, address = spec['sheet'], spec['cell']
        if name in originals or name not in book or not re.fullmatch(r'[A-Z]{1,3}[1-9]\d*', address):
            raise ValueError('feature must address one cell on an added sheet')
        key = (name, address)
        if key in occupied:
            raise ValueError('duplicate feature location')
        occupied.add(key)
        cell = book[name][address]
        if formula:
            checks.add('feature:formula:' + name + '!' + address, cell.data_type == 'f')
        return cell, key
    check_derived_sheets(req, expected, book, cache, checks, originals,
                         workspace=workspace, dataset_id=manifest.get('dataset_id'))
    check_diagnostics_bindings(req, workspace, checks)
    try:
        name = features['summary_sheet']
        checks.add('overview_added', name in book and name not in originals)
        checks.add('metric_inventory', set(features['metrics']) == {m['id'] for m in req['metrics']})
        for metric in req['metrics']:
            cell, key = locate(features['metrics'][metric['id']], True)
            checks.add('semantic:metric:' + metric['id'], same_number(cache[key[0]][key[1]].value, expected['metric_values'][metric['id']]))
            deps = dependencies(book, key)
            anchor = _derived_metric_anchor(req, metric['id'])
            if anchor is not None:
                # Explicitly declared frozen derived-sheet anchor: the
                # transitive dependency walk must reach the declared anchor
                # cell itself (frozen value, no formulas inside).
                checks.add('semantic:source_dependency:' + metric['id'], anchor in deps,
                           {'dependency_basis': 'declared frozen derived-sheet anchor',
                            'anchor': list(anchor), 'dependencies': sorted(deps)[:24]})
            else:
                checks.add('semantic:source_dependency:' + metric['id'], any(n in originals for n, _ in deps))
            checks.add('feature:metric_color:' + metric['id'], color(cell, '008000'))
        scene = features['scenario']; cell, selector = locate(scene['selector'])
        spec = req['scenario']; names = [r['name'] for r in spec['rows']]
        checks.add('scenario:default', cell.value == spec['default'])
        dropdowns = [v for v in book[selector[0]].data_validations.dataValidation if v.type == 'list' and selector[1] in v.sqref]
        valid = False
        for v in dropdowns:
            expression = str(v.formula1).strip('=')
            if expression.startswith('"'):
                choices = expression.strip('"').split(',')
            else:
                sheet_name, area = (expression.rsplit('!', 1) if '!' in expression else (selector[0], expression))
                choices = [c.value for row in book[sheet_name.strip("'")][area.replace('$', '')] for c in row]
            valid = valid or choices == names
        checks.add('scenario:dropdown', valid)
        checks.add('scenario:selector_color', color(cell, '0000FF'))
        checks.add('scenario:inventory', set(scene['assumptions']) == set(names))
        assumption_locations = []
        for row in spec['rows']:
            supplied = scene['assumptions'][row['name']]
            checks.add('scenario:dimension_inventory:' + row['name'], set(supplied) == set(row['assumptions']))
            for dim, value in row['assumptions'].items():
                c, key = locate(supplied[dim]); assumption_locations.append(key)
                checks.add('scenario:assumption:' + row['name'] + ':' + dim, same_number(c.value, value) and c.data_type != 'f' and color(c, '0000FF'))
        checks.add('projection_inventory', set(scene['projections']) == {p['id'] for p in spec['projections']})
        for projection in spec['projections']:
            c, key = locate(scene['projections'][projection['id']], True)
            deps = dependencies(book, key)
            checks.add('semantic:projection:' + projection['id'], same_number(cache[key[0]][key[1]].value, expected['scenario_values'][spec['default']][projection['id']]))
            checks.add('semantic:scenario_dependency:' + projection['id'], selector in deps and any(p in deps for p in assumption_locations))
        checks.add('chart_inventory', set(features['charts']) == {c['id'] for c in req['charts']})
        chart_locations = set()
        for chart in req['charts']:
            loc = features['charts'][chart['id']]; s = loc['sheet']; i = loc['index']
            ok = s in book and s not in originals and isinstance(i, int) and 0 <= i < len(book[s]._charts) and (s, i) not in chart_locations
            chart_locations.add((s, i))
            if ok:
                references = chart_sources(book[s]._charts[i])
                ok = bool(references) and all('[' not in r for r in references)
                checks.add('chart:references:' + chart['id'], ok, references)
                declared_series = _derived_chart_series(req, chart['id'])
                series_values = []
                linked = True
                for series in book[s]._charts[i].series:
                    reference = getattr(getattr(series, 'val', None), 'numRef', None)
                    if reference is None:
                        reference = getattr(getattr(series, 'yVal', None), 'numRef', None)
                    if reference is None:
                        linked = False; continue
                    text = reference.f
                    target, area = text.rsplit('!', 1); target = target.strip("'").replace("''", "'")
                    area = area.replace('$', '')
                    cells = [c for row in book[target][area] for c in row]
                    values = [cache[target][c.coordinate].value for c in cells]
                    series_values.append(values)
                    if declared_series is not None and target == declared_series[0] \
                            and _same_area(area, declared_series[1]['value_range']):
                        # Values over the declared frozen derived range: their
                        # correctness is enforced by check_derived_sheets and
                        # the cached-value comparison below.  No recursive walk
                        # is needed because the derived sheet holds no formulas.
                        linked = linked and bool(cells)
                        category_ref = getattr(getattr(series, 'cat', None), 'numRef', None) \
                            or getattr(getattr(series, 'cat', None), 'strRef', None)
                        if category_ref is not None:
                            cat_target, cat_area = category_ref.f.rsplit('!', 1)
                            cat_target = cat_target.strip("'").replace("''", "'")
                            cat_area = cat_area.replace('$', '')
                            checks.add('derived:chart_categories_reference:' + chart['id'],
                                       cat_target == declared_series[0]
                                       and _same_area(cat_area, declared_series[1]['category_range']),
                                       {'declared_sheet': declared_series[0],
                                        'declared_range': declared_series[1]['category_range'],
                                        'actual_sheet': cat_target, 'actual_range': cat_area})
                    else:
                        linked = linked and all(target in originals or any(n in originals for n, _ in dependencies(book, (target, c.coordinate))) for c in cells)
                wanted = expected.get('chart_values', {}).get(chart['id'])
                checks.add('semantic:chart:' + chart['id'], wanted is not None and any(len(v) == len(wanted) and all(same_number(a, b) for a, b in zip(v, wanted)) for v in series_values), series_values)
                checks.add('semantic:chart_dependency:' + chart['id'], linked)
            checks.add('chart:' + chart['id'], ok)
        added = [s for s in book if s.title not in originals]
        checks.add('format:conditional_rules',
                   conditional_formatting_region_count(added) >= req['minimum_conditional_formats'])
        checks.add('format:comments', sum(c.comment is not None for s in added for c in s._cells.values()) >= req['minimum_comments'])
        checks.add('format:freeze_panes', name in book and book[name].freeze_panes is not None)
        checks.add('no_external_links', not book._external_links)
        errors = [s.title + '!' + c.coordinate for s in cache for c in s._cells.values() if c.data_type == 'e' or (isinstance(c.value, str) and c.value in ERRORS)]
        checks.add('zero_formula_errors', not errors, errors[:12])
        recalc = read_json(output / 'formula_recalc.json')
        checks.add('recalc_report', recalc.get('status') == 'success' and recalc.get('total_errors') == 0)
        for item in manifest.get('publish_files', []):
            p = output / item['output']; checks.add('published:' + item['output'], p.is_file() and sha256(p) == item['sha256'])
        for filename in manifest['required_outputs']:
            if filename not in ('business_verification.json', *deferred_outputs):
                checks.add('deliverable:' + filename, (output / filename).is_file())
        for filename, refs in (('metrics.csv', features['metrics']),
                               ('scenario.csv', scene['projections'])):
            csv_path = output / filename
            try:
                import csv
                with csv_path.open(newline='', encoding='utf-8') as stream:
                    rows = list(csv.reader(stream))
                wanted_ids = list(refs)
                csv_ok = bool(rows) and rows[0] == ['metric', 'value']
                actual_rows = rows[1:] if csv_ok else []
                csv_ok = csv_ok and [row[0] for row in actual_rows if row] == wanted_ids
                for ident, row in zip(wanted_ids, actual_rows):
                    expected_value = cache[refs[ident]['sheet']][refs[ident]['cell']].value
                    try:
                        actual_value = float(row[1])
                    except (IndexError, TypeError, ValueError):
                        csv_ok = False
                        continue
                    csv_ok = csv_ok and same_number(actual_value, expected_value)
                checks.add('csv_matches_workbook:' + filename, csv_ok,
                           {'rows': len(actual_rows), 'expected_rows': len(wanted_ids)})
            except (OSError, UnicodeError, ValueError) as exc:
                checks.add('csv_matches_workbook:' + filename, False,
                           f'{type(exc).__name__}: {exc}')
    finally:
        book.close(); cache.close(); del book, cache; gc.collect()


def verify_semantic_xlsx_loop(manifest, expected, workspace, checks, deferred_outputs=()):
    """Run the versioned per-iteration business checks inside the benchmark ROI.

    This deliberately matches the old XLSX verifier's scope: workbook and base
    sheet presence/scale, task features, cached values/errors, and deliverables.
    Source-cell equality, formula/name/chart protection, and recursive audits
    remain in ``verify_semantic_xlsx`` and run only during independent acceptance.
    """
    from openpyxl import load_workbook
    from .verify import same_number, color, ERRORS

    req = manifest['requirements']
    output = workspace / 'output'
    path = output / manifest['output_workbook']
    checks.add('workbook_file', path.is_file() and path.stat().st_size >= req.get('minimum_bytes', 1))
    if not path.is_file():
        return

    book = load_workbook(path, data_only=False)
    cache = load_workbook(path, data_only=True, read_only=True)
    try:
        original_names = list(req['base_sheets'])
        checks.add('base_sheets_present', all(name in book for name in original_names), book.sheetnames)
        checks.add('base_sheet_order', [name for name in book.sheetnames if name in original_names] == original_names,
                   [name for name in book.sheetnames if name in original_names])
        for sheet_name in original_names:
            dst = book[sheet_name] if sheet_name in book else None
            ok, detail = _sheet_scale_evidence(req, sheet_name, dst)
            checks.add('base_sheet_scale:' + sheet_name, ok, detail)

        features = read_json(output / 'workbook_features.json')
        occupied = set()
        def locate(spec, formula=False):
            name, address = spec['sheet'], spec['cell']
            if name in original_names or name not in book or not re.fullmatch(r'[A-Z]{1,3}[1-9]\d*', address):
                raise ValueError('feature must address one cell on an added sheet')
            key = (name, address)
            if key in occupied:
                raise ValueError('duplicate feature location')
            occupied.add(key)
            cell = book[name][address]
            if formula:
                checks.add('feature:formula:' + name + '!' + address, cell.data_type == 'f')
            return cell, key

        check_derived_sheets(req, expected, book, cache, checks, original_names,
                             workspace=workspace, dataset_id=manifest.get('dataset_id'))
        check_diagnostics_bindings(req, workspace, checks)

        name = features['summary_sheet']
        checks.add('overview_added', name in book and name not in original_names)
        checks.add('metric_inventory', set(features['metrics']) == {m['id'] for m in req['metrics']})
        for metric in req['metrics']:
            cell, key = locate(features['metrics'][metric['id']], True)
            checks.add('semantic:metric:' + metric['id'],
                       same_number(cache[key[0]][key[1]].value, expected['metric_values'][metric['id']]))
            refs = direct_formula_references(book, key)
            anchor = _derived_metric_anchor(req, metric['id'])
            if anchor is not None:
                # Explicitly declared frozen derived-sheet anchor: the KPI must
                # directly reference it.  It may not skip the anchor, hardcode a
                # value, or point at an undeclared cell.
                checks.add('semantic:source_dependency:' + metric['id'],
                           any(reference_covers_cell(ref, anchor) for ref in refs),
                           {'dependency_basis': 'declared frozen derived-sheet anchor',
                            'anchor': list(anchor), 'direct_references': sorted(refs)})
            else:
                checks.add('semantic:source_dependency:' + metric['id'],
                           any(n in original_names for n, _, _ in refs),
                           {'dependency_basis': 'original worksheet reference',
                            'direct_references': sorted(refs)})
            checks.add('feature:metric_color:' + metric['id'], color(cell, '008000'))

        scene = features['scenario']
        cell, selector = locate(scene['selector'])
        spec = req['scenario']
        scenario_names = [row['name'] for row in spec['rows']]
        checks.add('scenario:default', cell.value == spec['default'])
        dropdowns = [v for v in book[selector[0]].data_validations.dataValidation
                     if v.type == 'list' and selector[1] in v.sqref]
        valid = False
        for validation in dropdowns:
            expression = str(validation.formula1).strip('=')
            if expression.startswith('"'):
                choices = expression.strip('"').split(',')
            else:
                sheet_name, area = (expression.rsplit('!', 1) if '!' in expression
                                    else (selector[0], expression))
                choices = [c.value for row in book[sheet_name.strip("'")][area.replace('$', '')] for c in row]
            valid = valid or choices == scenario_names
        checks.add('scenario:dropdown', valid)
        checks.add('scenario:selector_color', color(cell, '0000FF'))
        checks.add('scenario:inventory', set(scene['assumptions']) == set(scenario_names))
        assumption_locations = []
        for row in spec['rows']:
            supplied = scene['assumptions'][row['name']]
            checks.add('scenario:dimension_inventory:' + row['name'],
                       set(supplied) == set(row['assumptions']))
            for dimension, value in row['assumptions'].items():
                c, key = locate(supplied[dimension])
                assumption_locations.append(key)
                checks.add('scenario:assumption:' + row['name'] + ':' + dimension,
                           same_number(c.value, value) and c.data_type != 'f' and color(c, '0000FF'))
        checks.add('projection_inventory', set(scene['projections']) == {p['id'] for p in spec['projections']})
        for projection in spec['projections']:
            c, key = locate(scene['projections'][projection['id']], True)
            refs = direct_formula_references(book, key)
            checks.add('semantic:projection:' + projection['id'],
                       same_number(cache[key[0]][key[1]].value,
                                   expected['scenario_values'][spec['default']][projection['id']]))
            has_link, link_basis = _scenario_formula_link(
                book, refs, selector, assumption_locations)
            checks.add('semantic:scenario_dependency:' + projection['id'],
                       has_link, {'direct_references': sorted(refs), 'link_basis': link_basis,
                                  'scope': 'loop checks direct or one-cell formula-intermediate structure and cached business result; transitive path is independent-audit scope'})

        checks.add('chart_inventory', set(features['charts']) == {chart['id'] for chart in req['charts']})
        chart_locations = set()
        for chart in req['charts']:
            location = features['charts'][chart['id']]
            sheet_name, index = location['sheet'], location['index']
            ok = (sheet_name in book and sheet_name not in original_names
                  and isinstance(index, int) and 0 <= index < len(book[sheet_name]._charts)
                  and (sheet_name, index) not in chart_locations)
            chart_locations.add((sheet_name, index))
            if ok:
                references = chart_sources(book[sheet_name]._charts[index])
                ok = bool(references) and all('[' not in ref for ref in references)
                checks.add('chart:references:' + chart['id'], ok, references)
                declared_series = _derived_chart_series(req, chart['id'])
                values, linked = [], True
                for series in book[sheet_name]._charts[index].series:
                    reference = getattr(getattr(series, 'val', None), 'numRef', None)
                    if reference is None:
                        reference = getattr(getattr(series, 'yVal', None), 'numRef', None)
                    if reference is None:
                        linked = False
                        continue
                    target, area = reference.f.rsplit('!', 1)
                    target, area = target.strip("'").replace("''", "'"), area.replace('$', '')
                    if declared_series is not None:
                        # The chart series must reference exactly the declared
                        # frozen derived-sheet ranges; a disconnected or moved
                        # value or category range is rejected here and by the
                        # cached-value check.
                        checks.add('derived:chart_series:' + chart['id'],
                                   target == declared_series[0]
                                   and _same_area(area, declared_series[1]['value_range']),
                                   {'declared_sheet': declared_series[0],
                                    'declared_range': declared_series[1]['value_range'],
                                    'actual_sheet': target, 'actual_range': area})
                        category_ref = getattr(getattr(series, 'cat', None), 'numRef', None) \
                            or getattr(getattr(series, 'cat', None), 'strRef', None)
                        if category_ref is not None:
                            cat_target, cat_area = category_ref.f.rsplit('!', 1)
                            cat_target = cat_target.strip("'").replace("''", "'")
                            cat_area = cat_area.replace('$', '')
                            checks.add('derived:chart_categories_reference:' + chart['id'],
                                       cat_target == declared_series[0]
                                       and _same_area(cat_area, declared_series[1]['category_range']),
                                       {'declared_sheet': declared_series[0],
                                        'declared_range': declared_series[1]['category_range'],
                                        'actual_sheet': cat_target, 'actual_range': cat_area})
                    cells = [item for row in book[target][area] for item in row]
                    values.append([cache[target][item.coordinate].value for item in cells])
                    # The measured loop confirms a live, non-external chart
                    # range and its cached business values above.  Requiring
                    # every intermediate Chart Data formula to point directly
                    # into a source sheet is a recursive dependency audit and
                    # belongs to independent acceptance.
                    linked = linked and bool(cells) and all(item.value is not None for item in cells)
                wanted = expected.get('chart_values', {}).get(chart['id'])
                checks.add('semantic:chart:' + chart['id'], wanted is not None and any(
                    len(series_values) == len(wanted) and all(same_number(a, b) for a, b in zip(series_values, wanted))
                    for series_values in values), values)
                checks.add('semantic:chart_dependency:' + chart['id'], linked,
                           {'scope': 'chart range and cached result in loop; transitive source path is independent-audit scope'})
            checks.add('chart:' + chart['id'], ok)

        added = [sheet for sheet in book if sheet.title not in original_names]
        formula_count = sum(cell.data_type == 'f' for sheet in added
                            for row in sheet.iter_rows() for cell in row)
        checks.add('added_formula_count', formula_count >= req.get('minimum_formula_count', 1), formula_count)
        checks.add('format:conditional_rules',
                   conditional_formatting_region_count(added) >= req['minimum_conditional_formats'])
        checks.add('format:comments',
                   sum(cell.comment is not None for sheet in added for cell in sheet._cells.values()) >= req['minimum_comments'])
        checks.add('format:freeze_panes', name in book and book[name].freeze_panes is not None)
        checks.add('no_external_links', not book._external_links)
        errors = [sheet.title + '!' + cell.coordinate for sheet in added
                  for row in cache[sheet.title].iter_rows() for cell in row
                  if cell.data_type == 'e' or (isinstance(cell.value, str) and cell.value in ERRORS)]
        checks.add('zero_formula_errors', not errors, errors[:12])
        recalc = read_json(output / 'formula_recalc.json')
        checks.add('recalc_report', recalc.get('status') == 'success' and recalc.get('total_errors') == 0)
        for item in manifest.get('publish_files', []):
            published = output / item['output']
            checks.add('published:' + item['output'], published.is_file() and sha256(published) == item['sha256'])
        for filename in manifest['required_outputs']:
            if filename not in ('business_verification.json', *deferred_outputs):
                checks.add('deliverable:' + filename, (output / filename).is_file())
        for filename, refs in (('metrics.csv', features['metrics']),
                               ('scenario.csv', scene['projections'])):
            csv_path = output / filename
            try:
                import csv
                with csv_path.open(newline='', encoding='utf-8') as stream:
                    rows = list(csv.reader(stream))
                wanted_ids = list(refs)
                csv_ok = bool(rows) and rows[0] == ['metric', 'value']
                actual_rows = rows[1:] if csv_ok else []
                csv_ok = csv_ok and [row[0] for row in actual_rows if row] == wanted_ids
                for ident, row in zip(wanted_ids, actual_rows):
                    expected_value = cache[refs[ident]['sheet']][refs[ident]['cell']].value
                    try:
                        actual_value = float(row[1])
                    except (IndexError, TypeError, ValueError):
                        csv_ok = False
                        continue
                    csv_ok = csv_ok and same_number(actual_value, expected_value)
                checks.add('csv_matches_workbook:' + filename, csv_ok,
                           {'rows': len(actual_rows), 'expected_rows': len(wanted_ids)})
            except (OSError, UnicodeError, ValueError) as exc:
                checks.add('csv_matches_workbook:' + filename, False,
                           f'{type(exc).__name__}: {exc}')
    finally:
        book.close()
        cache.close()
        del book, cache
        gc.collect()
