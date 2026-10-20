"""Readiness, publication-safety and launcher-wiring fixtures.

All fixtures run against temporary roots; no real asset, workbook or container
is touched.  These tests prove:

  * readiness rejects every unprepared v2 state with a machine-readable reason
    (missing declaration, missing artifact, hash mismatch, wrong schema,
    dataset or workload version, broken input binding, incomplete structure)
    and accepts a complete small fixture;
  * readiness_report separates static binding validity from formal execution
    readiness without raising;
  * publication is rollback-safe: an existing artifact is refused before the
    large input is scanned, staged content is validated before replacing the
    active file, backups never silently overwrite, and a manifest failure
    restores the previous artifact/binding state exactly.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from replay.readiness import (
    ReadinessError, check_dataset_readiness, readiness_report,
    PREPARATION_SCHEMA, WORKLOAD_VERSION)
from scripts import prepare_xlsx_selection as preparation


def _sha(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


def make_readiness_root(root, dataset='hr_metro', artifact=None, manifest_overrides=None,
                        seed_present=True, source_present=True):
    dataset_dir = root / 'assets/cases' / dataset / 'source/datasets/xlsx' / dataset
    (dataset_dir / 'input').mkdir(parents=True, exist_ok=True)
    workbook = dataset_dir / 'input/data.xlsx'
    workbook.write_bytes(b'fixture workbook bytes')
    if artifact is None:
        artifact = make_artifact(dataset, _sha(workbook.read_bytes()))
    artifact_bytes = (json.dumps(artifact, indent=1) + '\n').encode()
    artifact_path = dataset_dir / 'input/prepared_selection.json'
    if source_present:
        artifact_path.write_bytes(artifact_bytes)
    elif artifact_path.exists():
        artifact_path.unlink()
    seed_dir = root / 'compatibility/cases' / dataset / 'seed/input'
    seed_dir.mkdir(parents=True, exist_ok=True)
    seed_copy = seed_dir / 'prepared_selection.json'
    if seed_present:
        seed_copy.write_text(json.dumps(artifact, indent=1) + '\n')
    elif seed_copy.exists():
        seed_copy.unlink()
    source_dir = root / 'compatibility/cases' / dataset / 'source/datasets/xlsx' / dataset / 'input'
    source_dir.mkdir(parents=True, exist_ok=True)
    source_copy = source_dir / 'prepared_selection.json'
    if source_present:
        source_copy.write_text(json.dumps(artifact, indent=1) + '\n')
    elif source_copy.exists():
        source_copy.unlink()
    manifest = {
        'workbook': 'data.xlsx',
        'input_files': {
            'input/data.xlsx': _sha(workbook.read_bytes()),
            'input/prepared_selection.json': _sha(artifact_bytes),
        },
        'preparation': {
            'artifact': 'input/prepared_selection.json',
            'schema_version': PREPARATION_SCHEMA,
            'workload_version': WORKLOAD_VERSION,
            'input_sha256': artifact['input_sha256'],
        },
        'requirements': {},
    }
    manifest.update(manifest_overrides or {})
    manifest_path = dataset_dir / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=1) + '\n')
    recipe = {
        'dataset_id': dataset,
        'seed_path': f'compatibility/cases/{dataset}/seed',
        'manual_source': {
            'manifest_path': str(manifest_path.relative_to(root)),
        },
        'input_hashes': dict(manifest['input_files']),
    }
    return recipe, manifest_path, artifact_path, artifact


def make_artifact(dataset, input_sha):
    if dataset == 'hr_metro':
        selection = {
            'sheet': 'MSA_M2025_dl', 'scope': {'AREA': '35620'},
            'columns': {'AREA': 'A'},
            'total': {'row': 3, 'occ_code': '00-0000',
                      'kpis': {'total_employment': {'cell': 'J3', 'value': 1},
                               'annual_mean_wage': {'cell': 'K3', 'value': 2},
                               'hourly_median_wage': {'cell': 'N3', 'value': 3}}},
            'chart_rows': [{'row': 4, 'occupation_code': '11-0000'}],
            'diagnostics': {'selected_record_count': 7},
        }
    else:
        selection = {
            'sheet': 'Online Retail', 'columns': {'invoiceno': {'header': 'InvoiceNo', 'column': 'A'}},
            'totals': {'gross_eligible_sales_gbp': 20.0, 'eligible_line_count': 5,
                       'eligible_quantity_units': 8.0,
                       'eligible_lines_missing_customer_id': 2, 'exclusion_counts': {}},
            'monthly_2010_sales_gbp': [0.0] * 12, 'currency': 'GBP',
            'derived_layout': {'sheet': 'Derived Totals', 'metric_anchors': {},
                               'chart_series': {}},
        }
    return {
        'schema_version': PREPARATION_SCHEMA,
        'dataset_id': dataset,
        'workload_version': WORKLOAD_VERSION,
        'input_file': 'data.xlsx',
        'input_sha256': input_sha,
        'selection': selection,
    }


class CheckDatasetReadinessTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        self.addCleanup(self._temp.cleanup)

    def _check(self, dataset='hr_metro', **kwargs):
        recipe = make_readiness_root(self.root, dataset, **kwargs)[0]
        return check_dataset_readiness(recipe, self.root)

    def test_complete_fixture_is_ready(self):
        for dataset in ('hr_metro', 'retail_online'):
            status = self._check(dataset)
            self.assertEqual(status['status'], 'ready')
            self.assertEqual(status['preparation'], 'declared_and_frozen')

    def test_unrelated_dataset_without_declaration_needs_nothing(self):
        recipe = {'dataset_id': 'tlc'}
        self.assertEqual(check_dataset_readiness(recipe, self.root)['preparation'],
                         'not_required')

    def test_required_dataset_without_declaration_is_not_ready(self):
        recipe, manifest_path, _artifact_path, _artifact = make_readiness_root(self.root)
        manifest = json.loads(manifest_path.read_text())
        del manifest['preparation']
        del manifest['input_files']['input/prepared_selection.json']
        manifest_path.write_text(json.dumps(manifest))
        recipe['input_hashes'] = dict(manifest['input_files'])
        with self.assertRaises(ReadinessError) as caught:
            check_dataset_readiness(recipe, self.root)
        self.assertEqual(caught.exception.reason, 'missing_preparation_declaration')

    def test_missing_seed_or_source_artifact_is_not_ready(self):
        with self.assertRaisesRegex(ReadinessError, 'seed artifact'):
            self._check(seed_present=False)
        with self.assertRaisesRegex(ReadinessError, 'source artifact'):
            self._check(source_present=False)

    def test_artifact_hash_mismatch_is_not_ready(self):
        recipe, manifest_path, artifact_path, _artifact = make_readiness_root(self.root)
        # tamper the seed copy only
        seed_copy = self.root / 'compatibility/cases/hr_metro/seed/input/prepared_selection.json'
        tampered = json.loads(seed_copy.read_text())
        tampered['selection']['total']['row'] = 999
        seed_copy.write_text(json.dumps(tampered))
        with self.assertRaises(ReadinessError) as caught:
            check_dataset_readiness(recipe, self.root)
        self.assertEqual(caught.exception.reason, 'preparation_hash_mismatch')
        # recipe binding disagreeing with the manifest is also a mismatch
        recipe, _m, _a, _art = make_readiness_root(self.root)
        recipe['input_hashes']['input/prepared_selection.json'] = '0' * 64
        with self.assertRaisesRegex(ReadinessError, 'preparation_hash_mismatch'):
            check_dataset_readiness(recipe, self.root)

    def test_wrong_schema_dataset_version_or_input_binding_is_not_ready(self):
        for mutate, reason in (
            (lambda a: a.__setitem__('schema_version', 'v0'), 'preparation_schema'),
            (lambda a: a.__setitem__('dataset_id', 'other'), 'preparation_dataset'),
            (lambda a: a.__setitem__('workload_version', 'v1'), 'preparation_workload_version'),
            (lambda a: a.__setitem__('input_sha256', '0' * 64), 'preparation_input_binding'),
        ):
            with self.subTest(reason=reason):
                artifact = make_artifact('hr_metro', _sha(b'fixture workbook bytes'))
                mutate(artifact)
                with self.assertRaises(ReadinessError) as caught:
                    self._check(artifact=artifact)
                self.assertEqual(caught.exception.reason, reason)

    def test_incomplete_selection_structure_is_not_ready(self):
        artifact = make_artifact('hr_metro', _sha(b'fixture workbook bytes'))
        del artifact['selection']['total']['kpis']['annual_mean_wage']
        with self.assertRaises(ReadinessError) as caught:
            self._check(artifact=artifact)
        self.assertEqual(caught.exception.reason, 'preparation_structure')

    def test_readiness_report_summarizes_without_raising(self):
        hr_recipe = make_readiness_root(self.root, 'hr_metro')[0]
        recipe_retail = make_readiness_root(self.root, 'retail_online')[0]
        # break the retail declaration to produce a mixed report
        retail_dir = self.root / 'assets/cases/retail_online/source/datasets/xlsx/retail_online'
        manifest = json.loads((retail_dir / 'manifest.json').read_text())
        del manifest['preparation']
        (retail_dir / 'manifest.json').write_text(json.dumps(manifest))
        (self.root / 'compatibility/suite.json').write_text(json.dumps({
            'entries': [
                {'dataset_id': 'hr_metro', 'recipe_path': str(
                    (self.root / 'compatibility/recipes/hr_metro.json'))},
                {'dataset_id': 'retail_online', 'recipe_path': str(
                    (self.root / 'compatibility/recipes/retail_online.json'))},
            ]}))
        recipes = self.root / 'compatibility/recipes'
        recipes.mkdir(parents=True, exist_ok=True)
        (recipes / 'hr_metro.json').write_text(json.dumps(hr_recipe))
        (recipes / 'retail_online.json').write_text(json.dumps(recipe_retail))
        report = readiness_report(['hr_metro', 'retail_online', 'unknown_one'], self.root)
        self.assertEqual(report['hr_metro']['status'], 'ready')
        self.assertEqual(report['retail_online']['status'], 'not_ready')
        self.assertEqual(report['retail_online']['reason'], 'missing_preparation_declaration')
        self.assertEqual(report['unknown_one']['reason'], 'unknown_dataset')


class PublicationSafetyTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        self.addCleanup(self._temp.cleanup)
        self.directory = preparation.asset_directory(self.root, 'hr_metro')
        (self.directory / 'input').mkdir(parents=True)
        self.workbook = self.directory / 'input/MSA_M2025_dl.xlsx'
        # a real small workbook keeps build_artifact honest without a large scan
        from openpyxl import Workbook
        book = Workbook()
        sheet = book.active
        sheet.title = 'MSA_M2025_dl'
        sheet.append(['AREA', 'AREA_TITLE', 'AREA_TYPE', 'NAICS', 'I_GROUP',
                      'OWN_CODE', 'O_GROUP', 'OCC_CODE', 'OCC_TITLE', 'TOT_EMP',
                      'A_MEAN', 'A_MEDIAN', 'H_MEAN', 'H_MEDIAN'])
        scope = ['35620', 'New York-Newark-Jersey City, NY-NJ', '4',
                 '000000', 'cross-industry', '1235']
        sheet.append(scope + ['total', '00-0000', 'All occupations', 1000, 80000, 60000, 40, 30])
        for index in range(5):
            sheet.append(scope + ['major', f'{index:02d}-0000', f'Group {index}',
                                  500 - index, 70000, 25000, 35, 25])
        book.save(self.workbook)
        book.close()
        self.expected = {
            'metric_values': {'total_employment': 1000, 'annual_mean_wage': 80000,
                              'hourly_median_wage': 30},
            'scenario_values': {'Base': {'projected_mean_wage': 80000},
                                'Increase': {'projected_mean_wage': 84000}},
            'chart_values': {'major_employment': [500, 499, 498, 497, 496]},
        }
        (self.directory / 'expected.json').write_text(json.dumps(self.expected))
        (self.directory / 'manifest.json').write_text(json.dumps({
            'schema_version': 'office-dataset-v2', 'kind': 'xlsx',
            'dataset_id': 'hr_metro', 'workbook': self.workbook.name,
            'expected_file': 'expected.json',
            'input_files': {'input/' + self.workbook.name: _sha(self.workbook.read_bytes())},
            'requirements': {}, 'origin_type': 'manual_workflow_adaptation',
        }))
        self.out = self.directory / 'input/prepared_selection.json'

    def _args(self, force=False):
        class Args:
            input = None
            output = None
            expected = None
            fixture = False
        args = Args()
        args.force = force
        return args

    def _run(self, force=False):
        return preparation.run_one(self.root, 'hr_metro', self._args(force=force))

    def _manifest(self):
        return json.loads((self.directory / 'manifest.json').read_text())

    def test_first_publication_binds_artifact_and_manifest(self):
        result = self._run()
        self.assertTrue(self.out.is_file())
        manifest = self._manifest()
        self.assertEqual(manifest['input_files']['input/prepared_selection.json'],
                         _sha(self.out.read_bytes()))
        self.assertEqual(manifest['preparation']['input_sha256'],
                         _sha(self.workbook.read_bytes()))
        self.assertEqual(manifest['requirements']['diagnostics_bindings'],
                         preparation.HR_DIAGNOSTICS_BINDINGS)
        self.assertEqual(result['checked_against_expected'], True)
        self.assertFalse(list(self.directory.glob('input/.prepared_selection*')))

    def test_existing_artifact_is_refused_before_scanning(self):
        self._run()
        with patch.object(preparation, 'build_artifact',
                          side_effect=AssertionError('must not scan the input')) as scan, \
                self.assertRaises(FileExistsError):
            preparation.run_one(self.root, 'hr_metro', self._args())
        scan.assert_not_called()
        manifest_before = self._manifest()
        self._run  # keep the binding below
        self.assertEqual(self._manifest(), manifest_before)

    def _mutate_workbook(self):
        # an out-of-scope extra row: selection values unchanged, bytes/hash change
        from openpyxl import load_workbook
        book = load_workbook(self.workbook)
        book.active.append(['00000', 'United States', '1', '000000', 'cross-industry',
                            '1235', 'total', '00-0000', 'Out of scope', 1, 1, 1, 1, 1])
        book.save(self.workbook)
        book.close()
        manifest = self._manifest()
        manifest['input_files']['input/' + self.workbook.name] = _sha(self.workbook.read_bytes())
        (self.directory / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')

    def test_force_supersedes_and_keeps_previous_version(self):
        self._run()
        first = self.out.read_bytes()
        self._mutate_workbook()
        self._run(force=True)
        backups = list(self.directory.glob('input/prepared_selection.superseded-*.json'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), first)
        self.assertNotEqual(self.out.read_bytes(), first)
        self.assertEqual(self._manifest()['input_files']['input/prepared_selection.json'],
                         _sha(self.out.read_bytes()))

    def test_artifact_write_failure_keeps_previous_state(self):
        self._run()
        first = self.out.read_bytes()
        manifest_before = self._manifest()
        with patch.object(preparation, 'publish_artifact',
                          side_effect=OSError('disk full')) as publish:
            with self.assertRaises(OSError):
                preparation.run_one(self.root, 'hr_metro', self._args(force=True))
        publish.assert_called_once()
        self.assertEqual(self.out.read_bytes(), first)
        self.assertEqual(self._manifest(), manifest_before)
        self.assertFalse(list(self.directory.glob('prepared_selection.superseded-*')))

    def test_manifest_update_failure_rolls_artifact_back(self):
        # first publication: nothing may remain that looks ready
        with patch.object(preparation, 'update_asset_manifest',
                          side_effect=OSError('manifest write failed')):
            with self.assertRaises(OSError):
                self._run()
        self.assertFalse(self.out.exists())
        self.assertNotIn('input/prepared_selection.json', self._manifest()['input_files'])
        self.assertNotIn('preparation', self._manifest())
        # supersede publication: previous active content and binding restored
        self._run()
        first = self.out.read_bytes()
        manifest_before = self._manifest()
        with patch.object(preparation, 'update_asset_manifest',
                          side_effect=OSError('manifest write failed')):
            with self.assertRaises(OSError):
                self._run(force=True)
        self.assertEqual(self.out.read_bytes(), first)
        self.assertEqual(self._manifest(), manifest_before)
        self.assertFalse(list(self.directory.glob('prepared_selection.superseded-*')))
        self.assertFalse(list(self.directory.glob('input/.prepared_selection*')))

    def test_backup_conflict_is_refused_and_keeps_active_file(self):
        self._run()
        first = self.out.read_bytes()
        backup = self.directory / 'input' / (
            f'prepared_selection.superseded-{_sha(first)[:8]}.json')
        backup.write_bytes(b'irrelevant historical backup')
        manifest_before = self._manifest()
        with self.assertRaisesRegex(FileExistsError, 'resolve it manually'):
            self._run(force=True)
        self.assertEqual(self.out.read_bytes(), first)
        self.assertEqual(backup.read_bytes(), b'irrelevant historical backup')
        self.assertEqual(self._manifest(), manifest_before)


    def test_rollback_preserves_preexisting_identical_backup(self):
        """force + manifest failure must not delete a backup this call did not create."""
        self._run()
        first = self.out.read_bytes()
        # a historical backup with the SAME content already exists on disk
        preexisting = self.directory / 'input' / (
            f'prepared_selection.superseded-{_sha(first)[:8]}.json')
        preexisting.write_bytes(first)
        self._mutate_workbook()
        manifest_before = self._manifest()
        with patch.object(preparation, 'update_asset_manifest',
                          side_effect=OSError('manifest write failed')):
            with self.assertRaises(OSError):
                self._run(force=True)
        # the active file is restored, the manifest is untouched, and the
        # pre-existing historical backup is still there with its content
        self.assertEqual(self.out.read_bytes(), first)
        self.assertEqual(self._manifest(), manifest_before)
        self.assertTrue(preexisting.is_file())
        self.assertEqual(preexisting.read_bytes(), first)
        self.assertFalse(list(self.directory.glob('input/.prepared_selection*')))
        # a backup created BY THIS CALL is still cleaned up on rollback
        self._run(force=True)  # republish the (mutated) artifact
        second = self.out.read_bytes()
        self.assertNotEqual(second, first)
        self._mutate_workbook()
        with patch.object(preparation, 'update_asset_manifest',
                          side_effect=OSError('manifest write failed')):
            with self.assertRaises(OSError):
                self._run(force=True)
        self.assertEqual(self.out.read_bytes(), second)
        # 'first' backup was created by this call and must be gone
        second_backups = list(self.directory.glob(
            f'input/prepared_selection.superseded-{_sha(second)[:8]}.json'))
        self.assertEqual(second_backups, [])
        # the pre-existing historical backup from before is untouched
        self.assertTrue(preexisting.is_file())
        self.assertEqual(preexisting.read_bytes(), first)

    def test_staging_failure_leaves_no_temporary_files(self):
        self._run()
        manifest_before = self._manifest()
        with patch.object(preparation.json, 'dumps', side_effect=ValueError('boom')):
            with self.assertRaises(ValueError):
                preparation.run_one(self.root, 'hr_metro', self._args(force=True))
        self.assertFalse(list(self.directory.glob('.prepared_selection.json.staging')))
        self.assertEqual(self._manifest(), manifest_before)


if __name__ == '__main__':
    unittest.main()
