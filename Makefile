PYTHON ?= python3
IMAGE ?= office-trace-replay:agent-traces
.PHONY: validate test image
validate:
	$(PYTHON) -B agent/replay.py --validate-only
	$(PYTHON) -B document-oe/run.py --validate-only
test:
	$(PYTHON) -B -m unittest discover -s agent/tests -v
	$(PYTHON) -B -m unittest discover -s document-oe/tests -v
	$(PYTHON) -B -m unittest discover -s tests -v
image:
	$(PYTHON) -B scripts/build_image.py --image $(IMAGE)
