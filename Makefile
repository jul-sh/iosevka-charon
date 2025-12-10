ENV_RUNNER := ./scripts/run-in-nix.sh
PLAN := sources/private-build-plans.toml

# Targets that should be included in automated test runs
TEST_TARGETS := build fonts postprocess images test proof diff-postprocess

# Source dependencies for each stage
BUILD_SOURCES := $(PLAN) $(shell find sources/iosevka -type f 2>/dev/null) $(shell find sources/scripts -name "build_fonts.py" 2>/dev/null)
POSTPROCESS_SOURCES := $(shell find scripts -name "post_process*.py" -o -name "fix_fonts.py" 2>/dev/null)

# DrawBot image generation
DRAWBOT_SCRIPTS=$(shell ls documentation/*.py 2>/dev/null)
DRAWBOT_OUTPUT=$(shell ls documentation/*.py 2>/dev/null | sed 's/\.py/.png/g')

help:
	@echo "###"
	@echo "# Build targets for Iosevka Charon"
	@echo "###"
	@echo
	@echo "  make build:                          Builds the fonts (all stages, in Nix)"
	@echo "  make build PLAN=<path-to-toml>:      Builds fonts using a custom build plan"
	@echo "  make fonts:                          Builds raw fonts only (stage 1: sources → sources/output/)"
	@echo "  make postprocess:                    Post-processes fonts (stage 2: sources/output/ → fonts/)"
	@echo "  make images:                         Generates specimen images via DrawBot (in Nix)"
	@echo "  make test:                           Runs fontspector checks on the built fonts (in Nix)"
	@echo "  make proof:                          Generates HTML proofs via diffenator2 (in Nix)"
	@echo "  make diff-postprocess:               Compares raw vs post-processed fonts (in Nix)"
	@echo "  make update-subtree TAG=<version>:   Updates Iosevka subtree to specified tag (e.g., v34.0.0)"
	@echo "  make clean:                          Removes build artifacts and stamp files"
	@echo

# Full build pipeline
build: postprocess.stamp

# Stage 1: Build raw fonts from Iosevka, into general_use_fonts/
fonts.stamp: $(BUILD_SOURCES)
	@echo "==> Stage 1: Building raw fonts from Iosevka sources..."
	@echo "Using build plan: $(PLAN)"
	rm -rf general_use_fonts
	$(ENV_RUNNER) python3 sources/scripts/build_fonts.py "$(PLAN)"
	@touch fonts.stamp
	@echo "==> Raw fonts built successfully in general_use_fonts/"

fonts: fonts.stamp

# Stage 2: Post-process fonts for Google Fonts compliance and output to fonts/
postprocess.stamp: fonts.stamp $(POSTPROCESS_SOURCES)
	@echo "==> Stage 2: Post-processing fonts for GF compliance..."
	rm -rf fonts
	$(ENV_RUNNER) python3 scripts/post_process_parallel.py
	@touch postprocess.stamp
	@echo "==> Final fonts available in fonts/ (Google Fonts version) and general_use_fonts/ (general use)"

postprocess: postprocess.stamp

# Stage 3: Generate specimen images with DrawBot
images: postprocess.stamp $(DRAWBOT_OUTPUT)

documentation/%.png: documentation/%.py postprocess.stamp
	$(ENV_RUNNER) python3 $< --output $@

# Testing and proofing
test: postprocess.stamp
	$(ENV_RUNNER) bash -c 'which fontspector || (echo "fontspector not found. Please install it with \"cargo install fontspector\"." && exit 1); \
		TOCHECK=$$(find fonts -type f -name "*.ttf" 2>/dev/null); \
		mkdir -p out/fontspector; \
		fontspector --profile googlefonts -l warn --full-lists --succinct \
			--html out/fontspector/fontspector-report.html \
			--ghmarkdown out/fontspector/fontspector-report.md \
			--badges out/badges $$TOCHECK || \
		echo "::warning file=sources/config.yaml,title=fontspector failures::The fontspector QA check reported errors in your font. Please check the generated report."'

proof: postprocess.stamp
	$(ENV_RUNNER) bash -c 'TOCHECK=$$(find fonts -type f -name "*.ttf" 2>/dev/null); \
		mkdir -p out/proof; \
		diffenator2 proof $$TOCHECK -o out/proof'

diff-postprocess: postprocess.stamp
	$(ENV_RUNNER) bash -c 'BEFORE=$$(find general_use_fonts -type f -name "*.ttf" 2>/dev/null | tr "\n" " "); \
		AFTER=$$(find fonts -type f -name "*.ttf" 2>/dev/null | tr "\n" " "); \
		mkdir -p out/diff-postprocess; \
		if [ -z "$$BEFORE" ] || [ -z "$$AFTER" ]; then \
			echo "Error: Could not find fonts to compare"; \
			exit 1; \
		fi; \
		diffenator2 diff --fonts-before $$BEFORE --fonts-after $$AFTER -o out/diff-postprocess --no-diffenator || true; \
		echo ""; \
		echo "==> Visual comparison complete!"; \
		echo "==> Open out/diff-postprocess/diffenator2-report.html to view results"'

clean:
	rm -f fonts.stamp postprocess.stamp
	rm -rf fonts general_use_fonts
	git stash && git clean -fdx && git stash pop

# Update Iosevka subtree to a new version
# Usage: make update-subtree TAG=v34.0.0
update-subtree:
	@if [ -z "$(TAG)" ]; then \
		echo "Error: TAG parameter is required"; \
		echo "Usage: make update-subtree TAG=v34.0.0"; \
		exit 1; \
	fi
	@echo "==> Updating Iosevka subtree to $(TAG)..."
	git fetch iosevka-upstream tag $(TAG) --no-tags
	git subtree pull --prefix=sources/iosevka iosevka-upstream $(TAG) -m "Update Iosevka subtree to $(TAG)"
	@echo "==> Subtree updated successfully to $(TAG)"

.PHONY: $(TEST_TARGETS) help clean update-subtree
