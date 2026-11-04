# DocOps L3 replay candidate image.
# Base: official docops-l3-shared-tools:arm64-v3 (b0d0e603...).
# Adds: Debian/arm64 perf (linux-perf 6.1.190-1) + runtime libs, frozen
# fontTools 4.68.0, the public replay entry, the frozen 12-task payload and the
# fixed DevKit Tuner CLI tool. Build is offline (all vendor material is COPYed).
#
# Known boundary: linux-perf depends on Debian `python3:any`; this base ships
# /usr/local/bin/python3 (3.12.14) instead of the Debian python3 package, so
# --force-depends is used. perf binary works (perf --version / DWARF via libdw);
# perf python-scripting support is the documented unconfigured edge.
ARG BASE_IMAGE=docops-l3-shared-tools:arm64-v3
FROM ${BASE_IMAGE}

# Debian/arm64 perf + required runtime libs (frozen debs)
COPY vendor/debs/ /opt/vendor-debs/
RUN dpkg -i --force-depends /opt/vendor-debs/*.deb \
    && rm -rf /opt/vendor-debs \
    && ln -sf /usr/bin/perf /usr/local/bin/perf

# fontTools 4.68.0 (frozen package; current-environment evidence, read-only copy
# from the docops-formal-01 container's site-packages, not a historical install proof)
COPY vendor/fonttools/fontTools /usr/local/lib/python3.12/site-packages/fontTools/

# public replay entry + frozen payload (no host mounts, no source repo needed)
COPY replay.py compile.py /opt/docops/
COPY payload /opt/docops/payload
COPY payload/skills/ /root/.codex/skills/
COPY install_state_check.py /opt/docops/docker/install_state_check.py
COPY devkit.sh /usr/local/bin/devkit
RUN chmod 0755 /usr/local/bin/devkit

# fixed DevKit Tuner CLI (measurement tool; NOT started in this round)
COPY devkit/ /opt/devkit/

ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /root
