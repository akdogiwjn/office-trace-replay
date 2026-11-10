"""Install-state acceptance for the docops-replay:openeuler-scaled image.

Runs inside the image with --network none and NO source/repo mounts. It checks:

- interpreter and tool versions (Python 3.12.3, perf, devkit, soffice, poppler, montage);
- runtime profile id;
- the frozen public Skills under /root/.codex/skills;
- the official twelve-task payload (/opt/docops/payload) and the unified 24-variant
  scaling payload (/opt/docops/scaling/payload-all): static validation, task sets,
  and every recipe's commands/scripts/inputs/expected/skills bindings;
- both payloads can be parsed and preflighted through the installed replay entry
  (validate-only, no workload);
- perf/DevKit are present (no formal measurement is started).

Prints a JSON report; exits 0 only when every check passes.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

OFFICIAL = Path('/opt/docops/payload')
SCALING = Path('/opt/docops/scaling/payload-all')
REPLAY = Path('/opt/docops/replay.py')
COMPILE = Path('/opt/docops/compile.py')
SKILLS = Path('/root/.codex/skills')


def load_compile():
    spec = importlib.util.spec_from_file_location('docops_compile', COMPILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    report = {'schema': 'docops-scaled-install-state-v1', 'status': 'running'}
    try:
        report['python'] = sys.version.split()[0]
        report['python_prefix'] = sys.prefix
        report['python_ok'] = (sys.version.split()[0] == '3.12.3'
                               and sys.prefix == '/opt/docops/venv')

        tools = {}
        for tool in ('perf', 'devkit', 'soffice', 'pdftoppm', 'pdftotext', 'pdfinfo', 'montage'):
            tools[tool] = shutil.which(tool) is not None
        report['tools'] = tools
        report['tools_ok'] = all(tools.values())
        report['perf_version'] = subprocess.run(
            ['perf', '--version'], capture_output=True, text=True).stdout.strip()
        report['devkit_version'] = subprocess.run(
            ['devkit', '--version'], capture_output=True, text=True).stdout.strip()

        profile = json.loads(Path('/opt/docops/runtime-profile.json').read_text())
        report['runtime_profile'] = profile.get('id')
        report['runtime_profile_ok'] = profile.get('id') == 'seven-case-openeuler-unified'

        skills = {name: (SKILLS / name / 'SKILL.md').is_file()
                  for name in ('doc', 'xlsx', 'pptx', 'pdf')}
        report['skills'] = skills
        report['skills_ok'] = all(skills.values())

        compile_mod = load_compile()
        official = compile_mod.validate_payload(OFFICIAL)
        scaling = compile_mod.validate_payload(SCALING)
        report['official_payload'] = {k: official.get(k) for k in ('status', 'tasks')}
        report['scaling_payload'] = {k: scaling.get(k) for k in ('status', 'tasks')}
        official_tasks = sorted(t['task'] for t in json.loads(
            (OFFICIAL / 'catalog.json').read_text())['tasks'])
        scaling_tasks = sorted(t['task'] for t in json.loads(
            (SCALING / 'catalog.json').read_text())['tasks'])
        report['official_task_count'] = len(official_tasks)
        report['scaling_task_count'] = len(scaling_tasks)
        report['official_is_twelve'] = (
            len(official_tasks) == 12 and official.get('status') == 'static_valid')
        report['scaling_is_twenty_four'] = (
            len(scaling_tasks) == 24 and scaling.get('status') == 'static_valid')

        # Every recipe's shell commands/scripts/inputs/expected resolve in the image.
        bind = {}
        ok = True
        for payload_root, label in ((OFFICIAL, 'official'), (SCALING, 'scaling')):
            index = json.loads((payload_root / 'payload-index.json').read_text())['files']
            for task_name in sorted(t['task'] for t in json.loads(
                    (payload_root / 'catalog.json').read_text())['tasks']):
                recipe = json.loads((payload_root / 'tasks' / task_name / 'recipe.json').read_text())
                missing = []
                for f in recipe['files']:
                    key = f['payload']
                    if (index[key]['sha256'] != f['sha256']
                            or ('bytes' in f and index[key]['bytes'] != f['bytes'])):
                        missing.append('binding:' + key)
                    if not (payload_root / key).is_file():
                        missing.append('missing:' + key)
                for s in recipe['steps']:
                    if not (payload_root / s['shell_body']).is_file():
                        missing.append('missing-command:' + s['shell_body'])
                    if any(flag in s['argv'][2] for flag in
                           ('--structure-only', '--skip', '--fixture', '--dry-run')):
                        missing.append('suspect-flag:' + s['id'])
                bind[f'{label}:{task_name}'] = missing
                if missing:
                    ok = False
        report['binding_ok'] = ok
        report['binding_missing'] = {k: v for k, v in bind.items() if v}

        # Preflight both payloads through the installed entry (validate-only, no workload).
        for payload_root, label in ((OFFICIAL, 'official'), (SCALING, 'scaling')):
            proc = subprocess.run(
                [sys.executable, '-B', str(REPLAY), 'validate-only',
                 '--payload', str(payload_root), '--env-check',
                 '--workdir', '/workspace/docops/work'],
                capture_output=True, text=True, timeout=600)
            parsed = {}
            try:
                raw = proc.stdout
                parsed = json.loads(raw[raw.index('{'):raw.rindex('}') + 1])
            except Exception as exc:
                parsed = {'parse_error': f'{type(exc).__name__}: {exc}'}
            report[f'preflight_{label}'] = {
                'rc': proc.returncode,
                'environment_errors': parsed.get('environment_errors', []),
                'payload_status': parsed.get('payload', {}).get('status'),
            }
            if proc.returncode != 0 or parsed.get('environment_errors'):
                ok = False

        report['status'] = 'passed' if (
            report.get('python_ok') and report.get('tools_ok')
            and report.get('runtime_profile_ok') and report.get('skills_ok')
            and report.get('official_is_twelve') and report.get('scaling_is_twenty_four')
            and report.get('binding_ok') and ok
        ) else 'failed'
    except BaseException as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
