#!/usr/bin/env python3
"""Build one offline, frozen image and record build/install-state evidence."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay.common import digest, read, write

EXCLUDED_ROOTS = {
    '.git', 'analysis', 'docs', 'qualification', 'reports', 'results',
    'replay-runs', 'replay_runs', 'tests', '.build', '.tmp', 'tmp', 'temp', '.venv',
}
EXCLUDED_DIRS = {'.venv', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'}


def context_estimate(root):
    """Estimate source payload bytes after the root and Python-cache ignores."""
    total = count = 0
    for path in root.rglob('*'):
        rel = path.relative_to(root)
        if rel.parts[0] in EXCLUDED_ROOTS or any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        if path.is_file() and not path.name.endswith(('.pyc', '.pyo')):
            total += path.stat().st_size
            count += 1
    return {'file_count': count, 'payload_bytes_estimate': total}


def git_source_identity():
    def run(args):
        result = subprocess.run(args, text=True, capture_output=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    status = run(['git', 'status', '--porcelain', '--untracked-files=all']) or ''
    return {
        'head': run(['git', 'rev-parse', 'HEAD']),
        'dirty': bool(status),
        'status_sha256': hashlib.sha256(status.encode()).hexdigest(),
        'status_lines': status.splitlines(),
    }


def local_image_id(tag):
    result = subprocess.run(['docker', 'image', 'inspect', tag, '--format', '{{.Id}}'],
                            text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def evidence_paths(tag, root=ROOT):
    label = tag.rsplit('/', 1)[-1].rsplit(':', 1)[-1]
    label = label.removeprefix('openeuler-')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', label):
        raise ValueError('invalid image evidence label: ' + label)
    return (root / f'reports/image-build-{label}.json',
            root / f'reports/image-install-acceptance-{label}.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', default='office-trace-replay:openeuler-release')
    args = parser.parse_args()
    build_record_path, acceptance_path = evidence_paths(args.tag, ROOT)
    if build_record_path.exists() or acceptance_path.exists():
        raise FileExistsError(f'{args.tag} evidence already exists; refusing to overwrite')
    if local_image_id(args.tag):
        raise FileExistsError('image tag already exists; refusing to overwrite: ' + args.tag)

    environment = read(ROOT / 'runtime/environment-lock.json')
    base_id = subprocess.check_output(
        ['docker', 'image', 'inspect', environment['base_image'], '--format', '{{.Id}}'],
        text=True).strip()
    if base_id != environment['base_image_id']:
        raise ValueError('local base image ID differs from environment lock')
    base_image = json.loads(subprocess.check_output(
        ['docker', 'image', 'inspect', base_id], text=True))[0]
    runner_hash = digest(ROOT / 'legacy/document-oe/bin/run_document_scene_loop.py')
    if runner_hash != environment['document_runner_sha256']:
        raise ValueError('environment lock runner hash differs from current runner')
    workload = read(ROOT / 'legacy/document-oe/lock.json').get('workload', [])
    if len(workload) != 43:
        raise ValueError(f'expected 43 frozen legacy workload files, found {len(workload)}')

    build_command = ['docker', 'build', '--pull=false', '--network=none', '-t', args.tag,
                     '--build-arg', 'BASE_IMAGE=' + environment['base_image'],
                     '-f', 'runtime/Dockerfile', '.']
    build_record = {
        'schema_version': 'office-replay-image-build-v2', 'status': 'in_progress',
        'started_at_utc': datetime.now(timezone.utc).isoformat(), 'image': args.tag,
        'base_image': environment['base_image'], 'base_image_id': base_id,
        'build_command': build_command, 'network': 'none', 'pull': False,
        'dockerfile_sha256': digest(ROOT / 'runtime/Dockerfile'),
        'dockerignore_sha256': digest(ROOT / '.dockerignore'),
        'project_lock_sha256': digest(ROOT / 'assets/project-lock.json'),
        'environment_lock_sha256': digest(ROOT / 'runtime/environment-lock.json'),
        'runner_sha256': runner_hash, 'legacy_workload_file_count': len(workload),
        'context_estimate': context_estimate(ROOT),
        'git_source_identity': git_source_identity(),
    }

    # This validates frozen inputs and recipes only; it does not run a workload.
    subprocess.run([sys.executable, str(ROOT / 'replay/entry.py'), '--validate-only'],
                   cwd=ROOT, check=True)
    write(build_record_path, build_record)
    try:
        subprocess.run(build_command, cwd=ROOT, check=True)
        image = json.loads(subprocess.check_output(
            ['docker', 'image', 'inspect', args.tag], text=True))[0]
        base_layers = base_image['RootFS']['Layers']
        if image['RootFS']['Layers'][:len(base_layers)] != base_layers:
            raise ValueError('built image does not inherit the inspected locked base layers')
    except Exception as exc:
        build_record.update(status='failed', failed_at_utc=datetime.now(timezone.utc).isoformat(),
                            error=f'{type(exc).__name__}: {exc}')
        write(build_record_path, build_record)
        raise

    build_record.update(status='success', completed_at_utc=datetime.now(timezone.utc).isoformat(),
                        image_id=image['Id'], architecture=image['Architecture'],
                        image_size_bytes=image.get('Size'),
                        base_image_size_bytes=base_image.get('Size'),
                        added_image_bytes=image.get('Size', 0) - base_image.get('Size', 0),
                        base_layers_verified=True)
    write(build_record_path, build_record)

    # No host source mounts or network: acceptance runs entirely from image contents.
    acceptance_command = [
        'docker', 'run', '--rm', '--network', 'none', '--read-only',
        '--entrypoint', '/opt/document-bench/.venv/bin/python', args.tag,
        'scripts/accept_install.py',
    ]
    result = subprocess.run(acceptance_command, cwd=ROOT, text=True, capture_output=True)
    acceptance = {
        'schema_version': 'office-replay-image-install-acceptance-v1',
        'status': 'success' if result.returncode == 0 else 'failed',
        'image': args.tag, 'image_id': image['Id'], 'architecture': image['Architecture'],
        'image_size_bytes': image.get('Size'), 'command': acceptance_command,
        'network': 'none', 'host_source_mounts': [], 'returncode': result.returncode,
        'stdout': result.stdout, 'stderr': result.stderr,
        'stdout_sha256': hashlib.sha256(result.stdout.encode()).hexdigest(),
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
    }
    write(acceptance_path, acceptance)
    if result.returncode:
        print(result.stdout, end='')
        print(result.stderr, file=sys.stderr, end='')
        raise SystemExit(result.returncode)
    print(result.stdout, end='')
    print(f"built and install-state accepted {args.tag} {image['Id']}")


if __name__ == '__main__':
    main()
