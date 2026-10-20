"""Render a compact audit status table from recorded hashes and reports."""
import argparse
import json
import re
from pathlib import Path


_SHA256 = re.compile(r'^[0-9a-fA-F]{64}$')


def output_unchanged(before_sha256, after_sha256):
    """Return True/False from valid before/after hashes, otherwise None."""
    if not isinstance(before_sha256, str) or not isinstance(after_sha256, str):
        return None
    if not _SHA256.fullmatch(before_sha256) or not _SHA256.fullmatch(after_sha256):
        return None
    return before_sha256.casefold() == after_sha256.casefold()


def markdown_dataset_rows(datasets):
    """Build rows without trusting a stored, manually authored boolean."""
    rows = []
    for dataset_id, item in datasets.items():
        unchanged = output_unchanged(
            item.get('output_sha256_before_audit'),
            item.get('output_sha256_after_audit'),
        )
        label = '是' if unchanged is True else '否' if unchanged is False else '未知'
        report = item.get('independent_verification', {})
        status = report.get('status', 'unknown')
        passed = report.get('checks_passed')
        total = report.get('checks_total')
        if isinstance(passed, int) and isinstance(total, int):
            status = f'{status} ({passed}/{total})'
        failures = report.get('failures') or []
        failure_text = '；'.join(str(value) for value in failures) or '—'
        rows.append((dataset_id, status, failure_text, label,
                     item.get('audit_container_id', 'unknown')))
    return '\n'.join('| ' + ' | '.join(map(str, row)) + ' |' for row in rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    rows = markdown_dataset_rows(manifest['datasets'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        '| 数据集 | 独立验收 | 失败项 | 审计前后输出一致 | 容器 ID |\n'
        '|---|---|---|---|---|\n' + rows + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

