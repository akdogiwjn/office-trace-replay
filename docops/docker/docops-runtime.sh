# bash -lc reloads /etc/profile. Restore the declared private runtime afterwards.
# Original trace commands and their argv remain unchanged.
if [ "${DOCOPS_RUNTIME_ACTIVE:-}" = 1 ]; then
    export VIRTUAL_ENV=/opt/docops/venv
    export PATH="/opt/docops/venv/bin:$PATH"
fi
