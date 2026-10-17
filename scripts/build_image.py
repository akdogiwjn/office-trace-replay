#!/usr/bin/env python3
"""Offline local-image build with locked base and resulting image provenance."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from replay.common import digest, read, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', default='office-trace-replay:openeuler-v9')
    args = parser.parse_args()
    lock = read(ROOT / 'runtime/environment-lock.json')
    actual = subprocess.check_output(['docker', 'image', 'inspect', lock['base_image'], '--format', '{{.Id}}'], text=True).strip()
    if actual != lock['base_image_id']:
        raise ValueError('local base tag has changed')
    subprocess.run([sys.executable, str(ROOT / 'replay/entry.py'), '--validate-only'], check=True)
    subprocess.run(['docker', 'build', '--pull=false', '--network=none', '-t', args.tag, '-f', 'runtime/Dockerfile', '.'], cwd=ROOT, check=True)
    image = __import__('json').loads(subprocess.check_output(['docker', 'image', 'inspect', args.tag], text=True))[0]
    write(ROOT / 'reports/image-build.json', {'schema_version': 'office-replay-image-build-v1', 'status': 'success',
          'image': args.tag, 'image_id': image['Id'], 'architecture': image['Architecture'],
          'base_image': lock['base_image'], 'base_image_id': actual,
          'project_lock_sha256': digest(ROOT / 'assets/project-lock.json'),
          'dockerfile_sha256': digest(ROOT / 'runtime/Dockerfile'), 'network': 'none', 'pull': False})
    print('built', args.tag, image['Id'])


if __name__ == '__main__':
    main()
