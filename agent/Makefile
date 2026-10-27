PYTHON ?= python3
DATASET ?=
.PHONY: validate test
validate:
	$(PYTHON) -B replay.py --validate-only
test:
	$(PYTHON) -B -m unittest discover -s tests -v
