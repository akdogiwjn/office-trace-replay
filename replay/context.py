"""Environment preparation for spawning a unified runner process.

The runner itself performs the authoritative environment preparation (Skill
links, /workspace alias, PATH / VIRTUAL_ENV / OFFICE_TRACE_PROJECT) so direct
invocation and the suite path behave identically. This module builds the env
dict used to start the runner subprocess and can verify the resulting context.
"""
import os
from pathlib import Path

NATIVE = Path('/opt/document-bench')


def environment(python_mode='venv', source=None):
    """Env dict for spawning the runner subprocess (clean, no stale context)."""
    env = os.environ.copy()
    env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
    env.pop('VIRTUAL_ENV', None)
    if python_mode == 'venv':
        env['PATH'] = '/opt/document-bench/.venv/bin:' + env['PATH']
        env['VIRTUAL_ENV'] = '/opt/document-bench/.venv'
    env.pop('PYTHONPATH', None)
    env.pop('OFFICE_TRACE_PROJECT', None)
    if source is not None:
        env['OFFICE_TRACE_PROJECT'] = str(source)
    return env


def report(env=None):
    """Describe the prepared context (used by the suite evidence)."""
    env = os.environ if env is None else env
    return {
        'python_mode': 'venv' if env.get('VIRTUAL_ENV') else 'system',
        'virtual_env': env.get('VIRTUAL_ENV'),
        'python_path_prefix': env.get('PATH', '').split(':')[0],
        'office_trace_project': env.get('OFFICE_TRACE_PROJECT'),
        'pythonpath': env.get('PYTHONPATH'),
    }
