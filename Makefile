PYTHON ?= python3
IMAGE ?= office-trace-replay:openeuler-v9
DATASET ?= pdf

.PHONY: test validate image replay
test:
	$(PYTHON) -m unittest discover -s tests -v
validate:
	$(PYTHON) replay/entry.py --validate-only
image:
	$(PYTHON) scripts/build_image.py --tag $(IMAGE)
replay:
	mkdir -p results
	docker run --rm --network none -v $(CURDIR)/results:/results $(IMAGE) --dataset $(DATASET) --loops 1
