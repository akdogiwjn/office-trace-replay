"""Small release-link checks; no Docker, raw samples or workbook scans."""
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text())


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def qualified_recipe(ds, active_path):
    """Keep v12 checks bound to v12 bytes after later entrypoint renames."""
    alignment = ROOT / 'reports/script-entrypoint-alignment-v1.json'
    if alignment.is_file():
        entry = read(str(alignment.relative_to(ROOT)))['datasets'].get(ds)
        if entry:
            if entry['recipe_path'] != active_path or digest(active_path) != entry['recipe_sha256']:
                raise ValueError('active named-entrypoint recipe differs from its frozen binding')
            if digest(entry['previous_recipe_path']) != entry['previous_recipe_sha256']:
                raise ValueError('v12 recipe snapshot changed')
            return entry['previous_recipe_path']
    return active_path


class ReleaseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.index = read('reports/evidence/v12/index.json')
        self.selection = read('analysis/hotspot-comparison/config/next-comparison-suite.json')

    def test_every_snapshot_has_its_original_bytes_and_size(self):
        seen = set()
        for item in self.index['files']:
            self.assertNotIn(item['path'], seen)
            seen.add(item['path'])
            self.assertEqual(digest(item['path']), item['sha256'], item['path'])
            self.assertEqual((ROOT / item['path']).stat().st_size, item['size_bytes'])

    def test_seven_function_results_match_qualified_recipe_versions(self):
        self.assertEqual(set(self.index['datasets']),
                         set(read('suites/default.json')['default_datasets']))
        for ds, entry in self.index['datasets'].items():
            summary = read(entry['functional_record']['path'])
            self.assertEqual([summary[k] for k in ('requested_iterations', 'completed_iterations',
                                                  'successes', 'failures')], [1, 1, 1, 0])
            self.assertEqual(summary['dataset'], ds)
            if ds in ('opm', 'tlc'):
                name = 'pdf' if ds == 'opm' else 'xlsx'
                recipe = f'legacy/document-oe/operations/{name}_key_operations.json'
                self.assertIsNone(entry['independent_acceptance'])
            else:
                suffix = '-n1' if ds in ('irs_w4', 'sba1919') else ''
                recipe = f'compatibility/recipes/{ds}{suffix}.json'
                recipe = qualified_recipe(ds, recipe)
                self.assertEqual(read(entry['independent_acceptance']['path'])['status'], 'success')
                evidence = read(entry['files']['evidence.json']['path'])
                current = read(recipe)
                self.assertEqual(evidence['helper_hashes'], current.get('helper_hashes', {}))
                self.assertEqual(evidence['input_hashes'], current['input_hashes'])
            self.assertEqual(summary['recipe_sha256'], digest(recipe))
            business = read(entry['business_verification']['path'])
            self.assertEqual(business['status'], 'success')
            self.assertEqual(business['failures'], [])
            inspect = read(entry['files']['container-inspect.json']['path'])
            inspect = inspect[0] if isinstance(inspect, list) else inspect
            self.assertEqual(inspect['Image'], self.index['image_id'])
            self.assertEqual(inspect['State']['ExitCode'], 0)
            self.assertEqual(inspect['HostConfig']['NetworkMode'], 'none')
            self.assertEqual([mount['Destination'] for mount in inspect['Mounts']], ['/results'])

    def test_current_function_links_and_historical_profiles_are_separate(self):
        release = self.selection['functional_release']
        self.assertEqual(digest(release['evidence_index']), release['evidence_index_sha256'])
        for ds in ('hr_metro', 'retail_online'):
            current = self.selection['manual_adaptations'][ds]
            self.assertIn('reports/evidence/v12/', current['functional_record'])
            self.assertEqual(digest(current['functional_record']), current['functional_record_sha256'])
            self.assertEqual(digest(current['independent_audit']), current['independent_audit_sha256'])
            self.assertEqual(current['current_native_profile_status'], 'not_collected_for_prepared_v2')
            self.assertEqual(current['current_pyspy_profile_status'], 'not_collected_for_prepared_v2')
            self.assertNotIn('profile_reference', current)
            old = self.selection['historical_profiles']['manual_adaptations'][ds]
            self.assertIn('new-xlsx-hotspot-io-v1', old['profile_reference'])

    def test_corrected_cpu_and_measurement_origins_match_workloads(self):
        report = self.selection['current_total_cpu']
        self.assertEqual(digest(report['path']), report['sha256'])
        data = read(report['path'])
        for ds, binding in report['measurement_bindings'].items():
            self.assertEqual(digest(binding['path']), binding['sha256'])
            origin = read(binding['path'])
            current = self.selection['dataset_evidence'][ds]
            self.assertNotEqual(origin['image_id'], current['image_id'])
            measured_summary = binding['native_summary']
            self.assertEqual(digest(measured_summary['path']), measured_summary['sha256'])
            measured = read(measured_summary['path'])
            self.assertEqual(measured['recipe_sha256'], current['recipe_sha256'])
            self.assertEqual(measured['dataset'], ds)
            self.assertEqual(current['read_write_share'], data['datasets'][ds]['read_write_share'])
            if ds != 'tlc':
                self.assertEqual(origin['recipe']['sha256'], current['recipe_sha256'])
                recipe = read(qualified_recipe(ds, origin['recipe']['path']))
                self.assertEqual(origin['recipe']['helper_hashes'], recipe['helper_hashes'])
                self.assertEqual(origin['recipe']['input_hashes'], recipe['input_hashes'])


if __name__ == '__main__':
    unittest.main()
