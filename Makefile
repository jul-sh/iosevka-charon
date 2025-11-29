ENV_RUNNER := ./scripts/run-in-nix.sh
DRAWBOT_SCRIPTS=$(shell ls documentation/*.py 2>/dev/null || echo "")
DRAWBOT_OUTPUT=$(shell ls documentation/*.py 2>/dev/null | sed 's/\.py/.png/g' || echo "")

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

build: build.stamp

build.stamp:
	$(ENV_RUNNER) bash sources/build.sh
	touch build.stamp

test: build.stamp
	TOCHECK=$$(find fonts/ttf -type f -name "*.ttf" 2>/dev/null | head -n 4); if [ -z "$$TOCHECK" ]; then echo "No TTF files found in fonts/ttf"; exit 1; fi; $(ENV_RUNNER) bash -lc "mkdir -p out/ out/fontspector; fontspector --profile googlefonts -l warn --full-lists --succinct --html out/fontspector/fontspector-report.html --ghmarkdown out/fontspector/fontspector-report.md --badges out/badges $$TOCHECK || echo '::warning file=sources/private-build-plans.toml,title=fontspector failures::The fontspector QA check reported errors in your font. Please check the generated report.'"

proof: build.stamp
	TOCHECK=$$(find fonts/ttf -type f -name "*.ttf" 2>/dev/null | head -n 4); if [ -z "$$TOCHECK" ]; then echo "No TTF files found in fonts/ttf"; exit 1; fi; $(ENV_RUNNER) bash -lc "mkdir -p out/ out/proof; diffenator2 proof $$TOCHECK -o out/proof"

images: build.stamp $(DRAWBOT_OUTPUT)

%.png: %.py build.stamp
	$(ENV_RUNNER) bash -lc "./$< --output $@"

clean:
	rm -rf fonts out build.stamp .venv
	find . -name "*.pyc" -delete

update-uv-lock:
	$(ENV_RUNNER) bash sources/scripts/update_uv_lock.sh
