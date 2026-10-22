PYTHON ?= python3
IMAGE ?= office-trace-replay:openeuler-v12
DATASET ?=
DATASET_ARGS = $(foreach dataset,$(DATASET),--dataset $(dataset))
ASSET_BUNDLE ?=

.PHONY: test validate image replay assets-verify assets-restore
test:
	$(PYTHON) -m unittest discover -s tests -v
validate: assets-verify
	$(PYTHON) replay/entry.py --validate-only
image: assets-verify
	$(PYTHON) scripts/build_image.py --tag $(IMAGE)
replay:
	mkdir -p results
	docker run --rm --network none -v $(CURDIR)/results:/results $(IMAGE) $(DATASET_ARGS) --loops 1 --results-dir /results
assets-verify:
	$(PYTHON) distribution/assets.py verify
assets-restore:
	@test -n "$(ASSET_BUNDLE)" || (echo 'Set ASSET_BUNDLE to the local offline assets TAR' >&2; exit 2)
	$(PYTHON) distribution/assets.py restore --bundle "$(ASSET_BUNDLE)"
