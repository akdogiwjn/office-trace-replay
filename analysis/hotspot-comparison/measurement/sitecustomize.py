"""sitecustomize entry: loads the CPU ledger hook when CPU_LEDGER_OUT is set.

Mounted read-only into the measured container's venv site-packages (a single
file bind mount), so every Python process started by the workload tree loads
it without any change to the runner, recipes or workload scripts.  The runner
clears PYTHONPATH in its environment preparation; a sys.path based injection
would be lost, the site-packages mount is not.
"""
try:
    import os
    if os.environ.get('CPU_LEDGER_OUT'):
        from cpu_ledger import install, LEDGER  # noqa: F401
        install()
except Exception:  # pragma: no cover - never break interpreter startup
    pass
