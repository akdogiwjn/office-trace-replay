#!/usr/bin/env python3
"""Fresh process CPU measurements from the installed formal image only.

Only this collector and the existing /proc monitor are mounted read-only.
No project, input, runner, Skill, sitecustomize or helper override is mounted.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time


IMAGE = 'office-trace-replay:openeuler-release'
PYTHON = '/opt/document-bench/.venv/bin/python'
INSTALLED = Path('/opt/office-trace-replay')
DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']
DATASETS = ['tlc', 'hr_metro', 'retail_online', 'industry_productivity',
            'opm', 'irs_w4', 'sba1919']
PROBE_SOURCE = ('import subprocess, sys, time\n'
                'subprocess.run([sys.executable,"-c",'
                '"import time; end=time.process_time()+0.25\\nwhile time.process_time()<end: pass"],check=True)\n'
                'end=time.process_time()+0.25\nwhile time.process_time()<end: pass\n')


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def capture(root, command):
    """Monitor one child tree; controller and monitor are siblings, outside it."""
    monitor_dir = root / 'monitor'
    monitor_dir.mkdir()
    stop = root / 'monitor-stop'
    stop.mkdir()
    alive = stop / 'alive'
    alive.touch()
    environment = dict(os.environ, HOTSPOT_MONITOR_STOP=str(stop))
    monitor = subprocess.Popen([PYTHON, '/measurement/monitor_procs.py',
                                str(monitor_dir), '10'], env=environment)
    child = None
    try:
        for _ in range(100):
            path = monitor_dir / 'monitor.jsonl'
            if path.exists() and path.stat().st_size:
                break
            if monitor.poll() is not None:
                raise RuntimeError('monitor stopped before workload launch')
            time.sleep(0.01)
        else:
            raise RuntimeError('monitor did not become ready')
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        anchor = {'mono_ns': time.clock_gettime_ns(time.CLOCK_MONOTONIC),
                  'real_ns': time.clock_gettime_ns(time.CLOCK_REALTIME)}
        write(root / 'clock-anchor.json', anchor)
        with (root / 'workload.log').open('wb') as log:
            child = subprocess.Popen(['taskset', '-c', '0-7', *command],
                                     stdout=log, stderr=subprocess.STDOUT)
            launch_pid = child.pid
            result = child.wait()
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        # Whole-command reference includes the runner preflight and final report
        # writing outside the iteration. It is not substituted for ROI CPU.
        return {'workload_exit_code': result, 'entry_pid': launch_pid,
                'command': command,
                'clock_ticks_per_second': os.sysconf('SC_CLK_TCK'),
                'whole_command_waited_user_seconds': after.ru_utime - before.ru_utime,
                'whole_command_waited_sys_seconds': after.ru_stime - before.ru_stime}
    finally:
        alive.unlink(missing_ok=True)
        monitor.wait(timeout=30)
        if monitor.returncode:
            raise RuntimeError('monitor exited unsuccessfully')


def inside(args):
    root = Path('/results')
    os.sched_setaffinity(0, {9})
    if args.dataset == 'probe':
        path = root / 'probe_workload.py'
        path.write_text(PROBE_SOURCE)
        record = capture(root, [PYTHON, str(path)])
        write(root / 'capture.json', record)
    else:
        core = load_module('formal_installed_executor',
                           INSTALLED / 'vendor/document-oe/run_document_scene_loop.py')
        scene = core.DATASET_SCENE[args.dataset]
        layout = core.dataset_layout(scene, args.dataset, args.pdf_count)
        recipe_path = layout['recipe']
        recipe = read(recipe_path)
        with (root / 'preflight.log').open('w') as log:
            subprocess.run([PYTHON, str(INSTALLED / 'replay/entry.py'),
                            '--dataset', args.dataset, '--validate-only'],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        shutil.copyfile(recipe_path, root / 'recipe.json')
        write(root / 'installed-identity.json', {
            'dataset': args.dataset, 'scene': scene, 'pdf_count': args.pdf_count if scene == 'pdf' else None,
            'python': sys.version, 'project_lock_sha256': sha(INSTALLED / 'assets/project-lock.json'),
            'recipe_path': str(recipe_path), 'recipe_sha256': sha(recipe_path),
            'runner_sha256': sha('/opt/document-bench/bin/run_document_scene_loop.py'),
            'workspace': str(layout['workspace']), 'measurement': 'process_cpu_only',
            'workload_cpus': list(range(8)), 'monitor_cpu': 9, 'poll_interval_ms': 10,
            'workload_source_overrides': [], 'scope': 'installed image; loop-only entry'})
        command = [PYTHON, str(INSTALLED / 'replay/entry.py'), '--scene', scene,
                   '--dataset', args.dataset, '--loops', '1', '--results-dir', '/results/workload']
        if scene == 'pdf':
            command += ['--pdf-applicant-count', str(args.pdf_count)]
        record = capture(root, command)
        write(root / 'capture.json', record)
        output = Path(layout['workspace']) / 'output'
        if output.exists():
            shutil.copytree(output, root / 'output')
        if record['workload_exit_code']:
            raise RuntimeError('workload failed; retained logs and outputs')
    # Make only newly produced results host-readable. Never chmod original
    # inputs, old evidence, or any file outside this new result directory.
    for path in root.rglob('*'):
        if path.is_file():
            path.chmod(0o644)
    return 0


def analyse(result_dir, analysis_module):
    root = Path(result_dir)
    identity = read(root / 'installed-identity.json')
    run_dirs = list((root / 'workload' / identity['scene']).glob('*/'))
    if len(run_dirs) != 1:
        raise RuntimeError('expected exactly one native run directory')
    summary = read(run_dirs[0] / 'summary.json')
    iterations = [json.loads(line) for line in (run_dirs[0] / 'iterations.jsonl').read_text().splitlines() if line]
    if len(iterations) != 1:
        raise RuntimeError('expected exactly one iteration')
    event = iterations[0]
    anchor = read(root / 'clock-anchor.json')
    end = int(analysis_module.parse_utc(event['finished_at']) * 1e9) - (anchor['real_ns'] - anchor['mono_ns'])
    start = end - int(event['elapsed_seconds'] * 1e9)
    monitor = analysis_module.Monitor(root / 'monitor')
    capture_record = read(root / 'capture.json')
    entry_pid = capture_record['entry_pid']
    if not any(row[1] == entry_pid for row in monitor.identities):
        raise RuntimeError('workload root PID was not observed')
    pids = monitor.subtree(entry_pid)
    commands = {pid: (comm, command) for _, pid, _, comm, command in monitor.identities}
    roles, processes = {}, []
    ticks_per_second = capture_record['clock_ticks_per_second']
    def role(command, comm):
        argv = analysis_module.command_argv(command)
        script = Path(argv[1]).name if analysis_module.is_python(command) and len(argv) > 1 else ''
        if identity['scene'] == 'pdf':
            by_script = {'check_fillable_fields.py': 'pdf-check-fillable',
                         'extract_form_field_info.py': 'pdf-extract-fields',
                         'fill_fillable_fields.py': 'pdf-fill',
                         'convert_pdf_to_images.py': 'pdf-convert',
                         'verify_pdf_batch.py': 'pdf-verify', 'verify_office.py': 'pdf-verify',
                         'write_pdf_batch_summary.py': 'pdf-summary-writer', 'summary.py': 'pdf-summary-writer',
                         'generate_and_run_batch.py': 'pdf-mapping-driver',
                         'build_field_values.py': 'pdf-mapping-driver',
                         'run_batch_fill_render.py': 'pdf-mapping-driver'}
            if script in by_script:
                return by_script[script]
            executable = Path(argv[0]).name if argv else comm
            if executable in ('pdftoppm', 'pdfinfo'):
                return executable
        return analysis_module.command_role(command, comm)
    for pid in sorted(pids):
        comm, command = commands.get(pid, ('', ''))
        seconds = sum(monitor.window_ticks(pid, start, end).values()) / ticks_per_second
        category = role(command, comm)
        roles[category] = roles.get(category, 0) + seconds
        processes.append({'pid': pid, 'role': category, 'command': command, 'cpu_seconds': seconds})
    total = sum(roles.values())
    business = read(root / 'output/business_verification.json')
    checks = {
        'one_successful_iteration': [summary.get(k) for k in (
            'requested_iterations', 'completed_iterations', 'successes', 'failures')] == [1, 1, 1, 0],
        'iteration_success': event['status'] == 'success',
        'business_success': business['status'] == 'success' and not business['failures'],
        'positive_cpu': total > 0,
        'recipe_binding': summary['recipe_sha256'] == identity['recipe_sha256'],
        'dataset_binding': summary['dataset'] == identity['dataset'],
        'roi_monitored': monitor.samples[0][0] <= start and monitor.samples[-1][0] >= end,
    }
    if not all(checks.values()):
        raise RuntimeError('measurement qualification failed: ' + str(checks))
    intervals = [(b[0] - a[0]) / 1e6 for a, b in zip(monitor.samples, monitor.samples[1:])]
    full_observed = sum(sum(monitor.window_ticks(pid, monitor.samples[0][0], monitor.samples[-1][0]).values())
                        for pid in pids) / ticks_per_second
    return {'schema_version': 'formal-process-cpu-v1', 'status': 'success', 'checks': checks,
            'dataset': identity['dataset'], 'scene': identity['scene'], 'pdf_count': identity['pdf_count'],
            'denominator_seconds': total, 'denominator': 'observed workload thread user+sys CPU within iteration ROI',
            'role_cpu_seconds': roles, 'role_share': {key: value / total for key, value in roles.items()},
            'processes': processes, 'roi': {'mono_start_ns': start, 'mono_end_ns': end,
                                          'elapsed_seconds': event['elapsed_seconds']},
            'actual_poll_gap_ms': {'median': sorted(intervals)[len(intervals)//2], 'maximum': max(intervals)},
            'whole_command_waited_cpu_seconds': capture_record['whole_command_waited_user_seconds']
                                                 + capture_record['whole_command_waited_sys_seconds'],
            'whole_command_observed_cpu_seconds': full_observed,
            'limitations': ['One iteration; /proc polling can miss short processes and final CPU ticks.',
                           'ROI uses container clock anchor and iteration timestamps, without independent offset calibration.',
                           'Whole-command waited CPU includes preflight/finalization and is not the ROI denominator.',
                           'No library/function sampling, no read/write ledger; no stability or optimization-benefit claim.']}


def host(args):
    root = Path(__file__).resolve().parents[3]
    campaign = args.campaign_dir.resolve()
    campaign.mkdir(parents=True, exist_ok=False)
    scripts = root / 'analysis/hotspot-comparison/scripts'
    sources = campaign / 'source'
    sources.mkdir()
    for source in (Path(__file__), scripts / 'monitor_procs.py', scripts / 'analyze_cpu_measurement.py'):
        shutil.copyfile(source, sources / source.name)
    collector_source = sources / Path(__file__).name
    analysis = load_module('formal_process_cpu_analysis', sources / 'analyze_cpu_measurement.py')
    release = read(root / 'reports/formal-image-release.json')
    image = read_docker(['image', 'inspect', IMAGE])[0]
    if image['Id'] != release['image_id']:
        raise RuntimeError('formal image ID differs from release record')
    plan = [('probe', 1)] + [(ds, 1) for ds in DATASETS[:4]] + [
        (ds, n) for n in (1, 10) for ds in DATASETS[4:]]
    inventory = {'schema_version': 'formal-process-cpu-campaign-v1', 'status': 'running',
                 'image': IMAGE, 'image_id': image['Id'], 'started_at_utc': datetime.now(timezone.utc).isoformat(),
                 'workload_source_mounts': [], 'measurement_only_mounts': [Path(__file__).name, 'monitor_procs.py'],
                 'collector_sha256': sha(collector_source), 'monitor_sha256': sha(sources / 'monitor_procs.py'),
                 'analysis_sha256': sha(sources / 'analyze_cpu_measurement.py'), 'completed': []}
    write(campaign / 'campaign.json', inventory)
    try:
        for dataset, count in plan:
            variant = dataset + (f'-n{count}' if dataset in DATASETS[4:] else '')
            out = campaign / variant
            out.mkdir()
            name = 'office-release-cpu-' + variant.replace('_', '-') + '-' + campaign.name[-8:]
            command = [*DOCKER, 'create', '--name', name, '--network', 'none',
                       '--cpuset-cpus', '0-7,9', '--env', 'PYTHONDONTWRITEBYTECODE=1',
                       '--mount', f'type=bind,src={collector_source},dst=/measurement/collector.py,readonly',
                       '--mount', f'type=bind,src={sources / "monitor_procs.py"},dst=/measurement/monitor_procs.py,readonly',
                       '--mount', f'type=bind,src={out},dst=/results',
                       '--entrypoint', PYTHON, IMAGE, '/measurement/collector.py', 'inside',
                       '--dataset', dataset, '--pdf-count', str(count)]
            cid = subprocess.check_output(command, text=True).strip()
            inspect = read_docker(['inspect', cid])[0]
            if inspect['Image'] != image['Id'] or inspect['HostConfig']['NetworkMode'] != 'none':
                raise RuntimeError('container image/network binding failed')
            mounts = {item['Destination']: item for item in inspect['Mounts']}
            if set(mounts) != {'/measurement/collector.py', '/measurement/monitor_procs.py', '/results'}:
                raise RuntimeError('unexpected mount changes the installed workload')
            if any(mounts[path]['RW'] for path in mounts if path != '/results'):
                raise RuntimeError('measurement source must be read-only')
            print('START', variant, cid[:12], flush=True)
            with (out / 'container.log').open('wb') as log:
                process = subprocess.Popen([*DOCKER, 'start', '-a', cid], stdout=log, stderr=subprocess.STDOUT)
                while process.poll() is None:
                    time.sleep(5)
            final = read_docker(['inspect', cid])[0]
            write(out / 'container-inspect.json', final)
            if process.returncode or final['State']['ExitCode']:
                raise RuntimeError(f'{variant} container failed; see {out / "container.log"}')
            if dataset == 'probe':
                capture_record = read(out / 'capture.json')
                monitor = analysis.Monitor(out / 'monitor')
                pids = monitor.subtree(capture_record['entry_pid'])
                observed = sum(sum(monitor.window_ticks(pid, monitor.samples[0][0], monitor.samples[-1][0]).values()) for pid in pids) / capture_record['clock_ticks_per_second']
                waited = capture_record['whole_command_waited_user_seconds'] + capture_record['whole_command_waited_sys_seconds']
                if not (observed > 0.4 and abs(waited-observed) < 0.08):
                    raise RuntimeError(f'probe CPU accounting mismatch: {observed} / {waited}')
                result = {'status': 'success', 'observed_cpu_seconds': observed, 'waited_cpu_seconds': waited}
            else:
                result = analyse(out, analysis)
            write(out / 'analysis.json', result)
            record = {'status': 'success', 'variant': variant, 'image_id': image['Id'],
                      'container_id': cid, 'analysis_sha256': sha(out / 'analysis.json'),
                      'measurement_source_overrides_only': True, 'workload_source_overrides': [],
                      'requested_iterations': 0 if dataset == 'probe' else 1}
            write(out / 'collection-record.json', record)
            files = [{'path': str(path.relative_to(out)), 'size_bytes': path.stat().st_size, 'sha256': sha(path)}
                     for path in sorted(out.rglob('*')) if path.is_file() and path.name != 'sha256-index.json']
            write(out / 'sha256-index.json', {'files': files, 'collection_record_sha256': sha(out / 'collection-record.json')})
            inventory['completed'].append({'variant': variant, 'status': 'success',
                                            'record_sha256': sha(out / 'collection-record.json'),
                                            'index_sha256': sha(out / 'sha256-index.json')})
            write(campaign / 'campaign.json', inventory)
            print('SUCCESS', variant, 'CPU', result.get('denominator_seconds'), flush=True)
        inventory.update(status='success', finished_at_utc=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        inventory.update(status='failed', error=f'{type(exc).__name__}: {exc}', failed_at_utc=datetime.now(timezone.utc).isoformat())
        raise
    finally:
        write(campaign / 'campaign.json', inventory)
    return 0


def read_docker(args):
    return json.loads(subprocess.check_output([*DOCKER, *args], text=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    collect = sub.add_parser('collect')
    collect.add_argument('--campaign-dir', type=Path, required=True)
    inner = sub.add_parser('inside')
    inner.add_argument('--dataset', choices=[*DATASETS, 'probe'], required=True)
    inner.add_argument('--pdf-count', type=int, choices=(1, 10), default=1)
    args = parser.parse_args()
    return inside(args) if args.mode == 'inside' else host(args)


if __name__ == '__main__':
    raise SystemExit(main())
