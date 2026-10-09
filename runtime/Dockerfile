# The builder checks this local tag against the locked immutable image ID.
ARG BASE_IMAGE=document-oe-snapshot:20260827
FROM ${BASE_IMAGE}
ENV PATH="/opt/office-trace-replay/runtime/bin:/opt/document-bench/.venv/bin:${PATH}" \
    VIRTUAL_ENV=/opt/document-bench/.venv \
    OFFICE_REPLAY_CONTAINER=1 PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 LC_ALL=C.UTF-8
COPY . /opt/office-trace-replay
WORKDIR /opt/office-trace-replay
RUN chmod 755 runtime/bin/soffice && /opt/document-bench/.venv/bin/python replay/run.py --validate-only
ENTRYPOINT ["/opt/document-bench/.venv/bin/python", "/opt/office-trace-replay/replay/run.py"]
CMD ["--loops", "1"]
