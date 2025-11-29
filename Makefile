ENV_RUNNER := ./scripts/run-in-nix.sh
DRAWBOT_SCRIPTS := $(wildcard documentation/*.py)
DRAWBOT_OUTPUT := $(patsubst %.py,%.png,$(DRAWBOT_SCRIPTS))

help:
	@echo "###"
	@echo "# Build targets for Iosevka Charon"
	@echo "###"
	@echo
	@echo "  make build:  Builds the fonts and places them in the fonts/ directory"
	@echo "  make test:   Tests the fonts with fontspector"
	@echo "  make proof:  Creates HTML proof documents in the proof/ directory"
	@echo "  make images: Creates PNG specimen images in the documentation/ directory"
	@echo

build:
	$(ENV_RUNNER) bash sources/build.sh
	$(ENV_RUNNER) bash scripts/post-process.sh

test: build
	$(ENV_RUNNER) bash scripts/run-tests.sh

proof: build
	$(ENV_RUNNER) bash scripts/run-proof.sh

images: $(DRAWBOT_OUTPUT)

%.png: %.py build
	$(ENV_RUNNER) python3 $< --output $@

clean:
	rm -rf fonts out build.stamp .venv
	find . -name "*.pyc" -delete
