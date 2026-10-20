"""Safety tests for the compatible recipe generator command line."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.compile_compatible import cli


class CompileCompatibleCliTests(unittest.TestCase):
    def test_help_exits_without_calling_generator_or_changing_files(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / 'sentinel'
            marker.write_text('unchanged')
            with patch('scripts.compile_compatible.main') as generate:
                with self.assertRaises(SystemExit) as raised:
                    cli(['--help'])
            self.assertEqual(raised.exception.code, 0)
            generate.assert_not_called()
            self.assertEqual(marker.read_text(), 'unchanged')

    def test_unknown_arguments_and_dataset_ids_fail_before_generation(self):
        for args in (['--unexpected'], ['--dataset', 'unknown_dataset']):
            with self.subTest(args=args), patch('scripts.compile_compatible.main') as generate:
                with self.assertRaises(SystemExit) as raised:
                    cli(args)
                self.assertEqual(raised.exception.code, 2)
                generate.assert_not_called()

    def test_repeated_dataset_options_are_passed_in_order(self):
        with patch('scripts.compile_compatible.main') as generate:
            self.assertEqual(cli(['--dataset', 'retail_online', '--dataset', 'hr_metro']), 0)
        generate.assert_called_once_with(datasets=['retail_online', 'hr_metro'])


if __name__ == '__main__':
    unittest.main()
