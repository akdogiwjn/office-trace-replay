PYTHON ?= python3
IMAGE ?= office-trace-replay:openeuler-v1
DATASET ?= retail

.PHONY: test validate image replay
test:
	$(PYTHON) -m unittest discover -s tests -v
validate:
	$(PYTHON) replay/run.py --validate-only
image:
	$(PYTHON) scripts/build_image.py --tag $(IMAGE)
replay:
	mkdir -p results
	docker run --rm --network none -v $(CURDIR)/results:/results $(IMAGE) --dataset $(DATASET) --loops 1
