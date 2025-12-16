#      (\_/)
#      (o.o)
#      / > [nix-shell]  <-- this provides all dependencies
SHELL := ./scripts/run-in-nix.sh

help:
	@echo "###"
	@echo "# Build targets for Iosevka Charon"
	@echo "###"
	@echo
	@echo "  make build:                          Builds the fonts"
	@echo "  make build PLAN=<path-to-toml>:      Builds fonts using a custom build plan"
	@echo "  make fonts:                          Builds raw fonts only (stage 1: sources → general_use_fonts/)"
	@echo "  make postprocess:                    Post-processes fonts (stage 2: general_use_fonts/ → fonts/)"
	@echo "  make images:                         Generates specimen images via DrawBot"
	@echo "  make test:                           Runs fontspector checks on the built fonts"
	@echo "  make proof:                          Generates HTML proofs via diffenator2"
	@echo "  make compare:                        Compares raw vs post-processed fonts"
	@echo "  make update-subtree TAG=<version>:   Updates Iosevka subtree to specified tag (e.g., v34.0.0)"
	@echo "  make clean:                          Removes build artifacts and stamp files"
	@echo

# Make targets that should be included in automated test runs
TEST_TARGETS := build fonts postprocess images test proof compare

# Source dependencies for each stage
BUILD_SOURCES := $(PLAN) $(shell find sources/iosevka -type f 2>/dev/null) scripts/iosevka_build.py
POSTPROCESS_SOURCES := $(shell find scripts -name "post_process*.py" -o -name "fix_fonts.py" 2>/dev/null)

# DrawBot image generation
DRAWBOT_SCRIPTS=$(shell ls documentation/*.py 2>/dev/null)
DRAWBOT_OUTPUT=$(shell ls documentation/*.py 2>/dev/null | sed 's/\.py/.png/g')

# Full build pipeline
build: postprocess.stamp

# Stage 1: Build raw fonts from Iosevka, into general_use_fonts/
fonts.stamp: $(BUILD_SOURCES)
	@echo "==> Stage 1: Building raw fonts from Iosevka sources..."
	@echo "Using build plan: $(PLAN)"
	rm -rf general_use_fonts
	rm -rf sources/iosevka/dist
	python3 scripts/iosevka_build.py "$(PLAN)"
	@touch fonts.stamp
	@echo "==> Raw fonts built successfully in general_use_fonts/"

fonts: fonts.stamp

# Stage 2: Post-process fonts for Google Fonts compliance and output to fonts/
postprocess.stamp: fonts.stamp $(POSTPROCESS_SOURCES)
	@echo "==> Stage 2: Post-processing fonts for GF compliance..."
	rm -rf fonts
	python3 scripts/post_process_parallel.py
	@touch postprocess.stamp
	@echo "==> Final fonts available in fonts/ (Google Fonts version) and general_use_fonts/ (general use)"

postprocess: postprocess.stamp

# Stage 3: Generate specimen images with DrawBot
images: postprocess.stamp $(DRAWBOT_OUTPUT)

documentation/%.png: documentation/%.py postprocess.stamp
	python3 $< --output $@




# Testing and proofing
test: postprocess.stamp
	which fontspector || (echo "fontspector not found. Please install it with \"cargo install fontspector\"." && exit 1)
	mkdir -p out/fontspector
	fontspector --profile googlefonts -l warn --full-lists --succinct \
		--html out/fontspector/fontspector-report.html \
		--ghmarkdown out/fontspector/fontspector-report.md \
		--badges out/badges $$(find fonts -type f -name "*.ttf") || \
		echo "::warning file=sources/config.yaml,title=fontspector failures::The fontspector QA check reported errors in your font. Please check the generated report."

proof: postprocess.stamp
	mkdir -p out/proof
	diffenator2 proof $$(find fonts -type f -name "*.ttf") -o out/proof

compare: postprocess.stamp
	mkdir -p out/compare
	diffenator2 diff \
		--fonts-before $$(find general_use_fonts -type f -name "*.ttf") \
		--fonts-after $$(find fonts -type f -name "*.ttf") \
		-o out/compare --no-diffenator || true
	@echo ""
	@echo "==> Visual comparison complete!"
	@echo "==> Open out/compare/diffenator2-report.html to view results"

clean:
	if ! git diff --quiet || ! git diff --cached --quiet; then \
		git stash && git clean -fdx && git stash pop; \
	else \
		git clean -fdx; \
	fi

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
