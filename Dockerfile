# One offline image, two independent workload entries, all seven datasets.
# BuildKit interprets bare image IDs as registry names. The build entry checks
# this local tag against container-contract.json before resolving FROM.
ARG BASE_IMAGE=office-trace-replay:openeuler-release
FROM ${BASE_IMAGE}
ENV OFFICE_AGENT_REPLAY_CONTAINER=1 DOCUMENT_OE_REPLAY_CONTAINER=1 \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/document-bench/.venv \
    PYTHONNOUSERSITE=1 \
    PATH=/opt/document-bench/.venv/bin:/opt/libreoffice25.8-symbols/program:${PATH}
COPY agent/ /opt/office-trace-replay/agent/
COPY document-oe/ /opt/office-trace-replay/document-oe/
# The old workload keeps its original absolute runtime paths.
COPY document-oe/assets/ /opt/document-bench/
COPY README.md container-contract.json /opt/office-trace-replay/
WORKDIR /opt/office-trace-replay
RUN mkdir -p /root/.openclaw/skills && \
    ln -sfn /opt/document-bench/skills/xlsx /root/.openclaw/skills/xlsx && \
    ln -sfn /opt/document-bench/skills/pdf /root/.openclaw/skills/pdf && \
    /opt/document-bench/.venv/bin/python agent/replay.py --validate-only && \
    /opt/document-bench/.venv/bin/python document-oe/run.py --validate-only --installed
ENTRYPOINT ["/opt/document-bench/.venv/bin/python", "/opt/office-trace-replay/agent/replay.py"]
CMD ["--loops", "1", "--results-dir", "/results"]
