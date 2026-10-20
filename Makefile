PYTHON ?= python3
IMAGE ?= office-trace-replay:openeuler-v12
DATASET ?=
DATASET_ARGS = $(foreach dataset,$(DATASET),--dataset $(dataset))

.PHONY: test validate image replay
test:
	$(PYTHON) -m unittest discover -s tests -v
validate:
	$(PYTHON) replay/entry.py --validate-only
image:
	$(PYTHON) scripts/build_image.py --tag $(IMAGE)
replay:
	mkdir -p results
	docker run --rm --network none -v $(CURDIR)/results:/results $(IMAGE) $(DATASET_ARGS) --loops 1 --results-dir /results
