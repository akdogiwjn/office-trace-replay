# The builder checks this local tag against the locked immutable image ID.
ARG BASE_IMAGE=document-oe-snapshot:20260827
FROM ${BASE_IMAGE}
ENV OFFICE_REPLAY_CONTAINER=1 PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 LC_ALL=C.UTF-8
COPY . /opt/office-trace-replay
# Restore the actual running document-oe bundle at its unchanged absolute root.
COPY legacy/document-oe/ /opt/document-bench/
WORKDIR /opt/office-trace-replay
RUN chmod 755 runtime/bin/soffice && /opt/document-bench/.venv/bin/python scripts/install_legacy_modes.py && /opt/document-bench/.venv/bin/python replay/entry.py --validate-only
ENTRYPOINT ["/opt/document-bench/.venv/bin/python", "/opt/office-trace-replay/replay/entry.py"]
CMD ["--loops", "1"]
