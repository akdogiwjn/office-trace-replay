#!/usr/bin/env python3
"""Build from a verified local base, without downloading runtime dependencies."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def build(image, base='office-trace-replay:openeuler-release', *, root=ROOT,
          docker_host='unix:///var/run/docker.sock'):
    root = Path(root)
    docker = ['docker', '--host', docker_host]
    expected = json.loads((root / 'container-contract.json').read_text())['base_image_id']
    actual = json.loads(subprocess.check_output(docker + ['image', 'inspect', base], text=True))[0]['Id']
    if actual != expected:
        raise ValueError(f'local base image mismatch: {actual}; expected {expected}')
    if image == base:
        raise ValueError('output image must not replace the offline base tag')
    existing = subprocess.run(docker + ['image', 'inspect', image], capture_output=True, text=True)
    if existing.returncode == 0:
        raise ValueError('output image tag already exists; choose a fresh tag: ' + image)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    report = root / 'reports' / ('image-build-' + stamp + '.json')
    report.parent.mkdir(parents=True, exist_ok=True)
    log = report.with_suffix('.log')
    command = docker + ['build', '--network', 'none', '--pull=false', '--progress', 'plain',
                        '--build-arg', 'BASE_IMAGE=' + base, '-t', image, str(root)]
    record = dict(status='in_progress', requested_image=image, base_image_id=actual,
                  command=command, log=str(log.relative_to(root)),
                  dockerfile_sha256=hashlib.sha256((root / 'Dockerfile').read_bytes()).hexdigest())
    report.write_text(json.dumps(record, indent=2) + '\n')
    print('Build log: ' + str(log), flush=True)
    with log.open('w') as stream:
        process = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
    record.update(exit_code=process.returncode, status='success' if process.returncode == 0 else 'failed')
    if process.returncode == 0:
        record['image'] = json.loads(subprocess.check_output(docker + ['image', 'inspect', image], text=True))[0]
    report.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(status=record['status'], report=str(report),
                         image_id=record.get('image', {}).get('Id'))), flush=True)
    return process.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='office-trace-replay:agent-traces')
    parser.add_argument('--base', default='office-trace-replay:openeuler-release')
    parser.add_argument('--docker-host', default='unix:///var/run/docker.sock')
    args = parser.parse_args()
    return build(args.image, args.base, docker_host=args.docker_host)


if __name__ == '__main__':
    raise SystemExit(main())
