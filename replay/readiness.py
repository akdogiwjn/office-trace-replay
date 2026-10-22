"""Formal-execution readiness for workloads that require frozen preparation.

Static binding validation (recipe hashes, helper hashes, project freeze) proves
the *code and assets* are consistent.  It says nothing about whether a workload
whose helper consumes a frozen preparation artifact is actually *executable*.
This module closes that gap: for the manual-workflow-adaptation-v2 XLSX
workloads the frozen ``prepared_selection.json`` must exist, match every frozen
hash binding, carry the right schema/dataset/workload version, bind the frozen
original-input SHA-256, and contain the required selection structure.

The check is wired into ``replay.freeze.validate_dataset`` (so the direct
runner, the suite dispatcher and the container preflight all reject an
unprepared workload before any workload command, workspace reset or workbook
read) and into ``replay.entry``'s ``--validate-only`` report, which keeps
"static bindings valid" and "formal execution ready" as separate, honest
statements.

Only small JSON files and already-frozen manifest hashes are read here; the
large input workbook itself is hashed by the regular preflight binding checks,
never opened by this module.
"""
from pathlib import Path
import json

from .common import ROOT, digest

# Workloads whose v2 enhancement helpers must consume a frozen preparation
# artifact.  A recipe for one of these datasets without a manifest declaration
# is not "no preparation needed"; it is an unprepared workload.
PREPARATION_REQUIRED = {'hr_metro', 'retail_online'}
PREPARATION_SCHEMA = 'xlsx-prepared-selection-v1'
WORKLOAD_VERSION = 'manual-workflow-adaptation-v2'
ARTIFACT_REL = 'input/prepared_selection.json'

# Minimum selection structure each prepared artifact must expose.  The keys
# mirror what the helpers and the derived-sheet verifier consume.
REQUIRED_SELECTION_PATHS = {
    'hr_metro': (
        'selection.sheet', 'selection.scope', 'selection.columns',
        'selection.total.row', 'selection.total.occ_code',
        'selection.total.kpis.total_employment.cell',
        'selection.total.kpis.total_employment.value',
        'selection.total.kpis.annual_mean_wage.cell',
        'selection.total.kpis.annual_mean_wage.value',
        'selection.total.kpis.hourly_median_wage.cell',
        'selection.total.kpis.hourly_median_wage.value',
        'selection.chart_rows', 'selection.diagnostics.selected_record_count',
    ),
    'retail_online': (
        'selection.sheet', 'selection.columns', 'selection.totals',
        'selection.totals.gross_eligible_sales_gbp',
        'selection.totals.eligible_line_count',
        'selection.totals.eligible_quantity_units',
        'selection.totals.eligible_lines_missing_customer_id',
        'selection.totals.exclusion_counts',
        'selection.monthly_2010_sales_gbp', 'selection.currency',
        'selection.derived_layout.sheet',
        'selection.derived_layout.metric_anchors',
        'selection.derived_layout.chart_series',
    ),
}


class ReadinessError(ValueError):
    """Formal execution is not ready; ``reason`` is machine-readable."""

    def __init__(self, reason, detail):
        super().__init__(f'formal preparation not ready ({reason}): {detail}')
        self.reason = reason
        self.detail = detail


def _resolve(document, dotted):
    value = document
    for part in dotted.split('.'):
        if part == '[]':
            if not isinstance(value, list):
                raise KeyError(dotted)
            return value
        if not isinstance(value, dict) or part not in value:
            raise KeyError(dotted)
        value = value[part]
    return value


def check_dataset_readiness(recipe, root=ROOT):
    """Validate preparation readiness for one recipe; raise ReadinessError otherwise.

    Returns a small status dict for callers that report readiness separately
    from static binding validity.
    """
    root = Path(root)
    dataset = recipe.get('dataset_id')
    if dataset in PREPARATION_REQUIRED and 'manual_source' not in recipe:
        raise ReadinessError(
            'inconsistent_registration',
            f'{dataset} requires a frozen preparation artifact but the recipe has no manual source binding')
    manifest_path = root / recipe['manual_source']['manifest_path'] if 'manual_source' in recipe else None
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path else {}
    declared = manifest.get('preparation')
    if dataset not in PREPARATION_REQUIRED and not declared:
        return {'dataset_id': dataset, 'status': 'ready',
                'preparation': 'not_required'}
    if declared is None:
        raise ReadinessError(
            'missing_preparation_declaration',
            f'{dataset} is a {WORKLOAD_VERSION} workload; its manifest must declare the '
            f'frozen preparation artifact ({ARTIFACT_REL}) before formal execution')
    artifact_rel = declared.get('artifact')
    if artifact_rel != ARTIFACT_REL:
        raise ReadinessError(
            'bad_preparation_declaration',
            f'declared artifact {artifact_rel!r} is not the expected {ARTIFACT_REL!r}')
    expected_hash = manifest.get('input_files', {}).get(artifact_rel)
    if not expected_hash:
        raise ReadinessError(
            'bad_preparation_declaration',
            f'manifest input_files does not bind {artifact_rel}')
    seed_artifact = root / recipe['seed_path'] / artifact_rel
    source_artifact = manifest_path.parent / artifact_rel
    for label, path in (('seed', seed_artifact), ('source', source_artifact)):
        if not path.is_file():
            raise ReadinessError(
                'missing_preparation_artifact',
                f'{label} artifact {path} does not exist; generate it with '
                'scripts/prepare_xlsx_selection.py (approved preparation outside the loop)')
        if digest(path) != expected_hash:
            raise ReadinessError(
                'preparation_hash_mismatch',
                f'{label} artifact {path} hash {digest(path)} != frozen manifest hash {expected_hash}')
    recipe_hash = recipe.get('input_hashes', {}).get(artifact_rel)
    if recipe_hash != expected_hash:
        raise ReadinessError(
            'preparation_hash_mismatch',
            f'recipe input_hashes binds {recipe_hash!r} but the manifest binds {expected_hash!r}')
    try:
        artifact = json.loads(seed_artifact.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ReadinessError(
            'bad_preparation_artifact',
            f'{seed_artifact} is not readable JSON: {exc}')
    if artifact.get('schema_version') != PREPARATION_SCHEMA:
        raise ReadinessError(
            'preparation_schema',
            f"artifact schema {artifact.get('schema_version')!r} != {PREPARATION_SCHEMA!r}")
    if artifact.get('dataset_id') != dataset:
        raise ReadinessError(
            'preparation_dataset',
            f"artifact dataset {artifact.get('dataset_id')!r} != {dataset!r}")
    if artifact.get('workload_version') != WORKLOAD_VERSION:
        raise ReadinessError(
            'preparation_workload_version',
            f"artifact workload version {artifact.get('workload_version')!r} != {WORKLOAD_VERSION!r}")
    workbook_key = 'input/' + manifest['workbook']
    frozen_input = manifest.get('input_files', {}).get(workbook_key)
    if artifact.get('input_sha256') != frozen_input:
        raise ReadinessError(
            'preparation_input_binding',
            f"artifact input_sha256 {artifact.get('input_sha256')!r} does not bind the frozen "
            f'original input hash {frozen_input!r} ({workbook_key})')
    for dotted in REQUIRED_SELECTION_PATHS.get(dataset, ()):
        try:
            _resolve(artifact, dotted)
        except KeyError:
            raise ReadinessError(
                'preparation_structure',
                f'artifact is missing the required selection field {dotted!r}')
    return {'dataset_id': dataset, 'status': 'ready',
            'preparation': 'declared_and_frozen',
            'artifact': str(seed_artifact.relative_to(root)),
            'artifact_sha256': expected_hash,
            'input_sha256': artifact['input_sha256']}


def readiness_report(dataset_ids, root=ROOT):
    """Per-dataset readiness without raising; used by --validate-only output."""
    root = Path(root)
    index = json.loads((root / 'compatibility/suite.json').read_text(encoding='utf-8'))
    entries = {entry['dataset_id']: entry for entry in index['entries']}
    report = {}
    for dataset in dataset_ids:
        entry = entries.get(dataset)
        if entry is None:
            report[dataset] = {'status': 'not_ready',
                               'reason': 'unknown_dataset',
                               'detail': 'no compatibility suite entry'}
            continue
        recipe = json.loads((root / entry['recipe_path']).read_text(encoding='utf-8'))
        try:
            report[dataset] = check_dataset_readiness(recipe, root)
        except ReadinessError as exc:
            report[dataset] = {'status': 'not_ready', 'reason': exc.reason,
                               'detail': exc.detail}
    return report
