#      (\_/)
#      (o.o)
#      / > [nix-shell]  <-- this provides all dependencies
SHELL := ./scripts/run-in-nix.sh

# Default build plan
PLAN ?= sources/private-build-plans.toml

help:
	@echo "###"
	@echo "# Build targets for Iosevka Charon"
	@echo "###"
	@echo
	@echo "  make build:                          Builds the fonts"
	@echo "  make build PLAN=<path-to-toml>:      Builds fonts using a custom build plan"
	@echo "  make fonts:                          Builds raw fonts only (stage 1: sources → unprocessed_fonts/)"
	@echo "  make postprocess:                    Post-processes fonts (stage 2: unprocessed_fonts/ → fonts/)"
	@echo "  make images:                         Generates specimen images via DrawBot"
	@echo "  make test:                           Runs fontspector checks on the built fonts"
	@echo "  make proof:                          Generates HTML proofs via diffenator2"
	@echo "  make compare:                        Compares raw vs post-processed fonts"
	@echo "  make webfonts:                       Generates WOFF2 webfonts with subsets (full, latin-ext, latin)"
	@echo "  make update-subtree [TAG=<version>]: Updates Iosevka subtree to latest release or specified tag"
	@echo "  make sync-version:                   Syncs upstream version to GF-compliant format"
	@echo "  make clean:                          Removes build artifacts and stamp files"
	@echo

# Make targets that should be included in automated test runs
TEST_TARGETS := build fonts postprocess webfonts images test proof compare

# Source dependencies for each stage
BUILD_SOURCES := $(PLAN) $(shell find sources/iosevka -type f 2>/dev/null) scripts/iosevka_build.py
POSTPROCESS_SOURCES := $(shell find scripts -name "post_process*.py" -o -name "fix_fonts.py" 2>/dev/null) sources/version.json

# DrawBot image generation
DRAWBOT_SCRIPTS=$(shell ls documentation/*.py 2>/dev/null)
DRAWBOT_OUTPUT=$(shell ls documentation/*.py 2>/dev/null | sed 's/\.py/.png/g')

# Full build pipeline
build: postprocess.stamp

# Stage 0: Sync upstream version to GF-compliant format
sync-version:
	@echo "==> Syncing upstream Iosevka version to GF format..."
	python3 scripts/sync_version.py

# Stage 1: Build raw fonts from Iosevka, into unprocessed_fonts/
fonts.stamp: sync-version $(BUILD_SOURCES)
	@echo "==> Stage 1: Building raw fonts from Iosevka sources..."
	@echo "Using build plan: $(PLAN)"
	rm -rf unprocessed_fonts
	rm -rf sources/iosevka/dist
	python3 scripts/iosevka_build.py "$(PLAN)"
	@touch fonts.stamp
	@echo "==> Raw fonts built successfully in unprocessed_fonts/"

fonts: fonts.stamp

# Stage 2: Post-process fonts for Google Fonts compliance and output to fonts/
postprocess.stamp: fonts.stamp $(POSTPROCESS_SOURCES)
	@echo "==> Stage 2: Post-processing fonts for GF compliance..."
	rm -rf fonts
	python3 scripts/fix_fonts.py
	@touch postprocess.stamp
	@echo "==> Final fonts available in fonts/"

postprocess: postprocess.stamp

# Stage 2.5: Generate WOFF2 webfonts with subsets
webfonts.stamp: postprocess.stamp
	@echo "==> Stage 2.5: Generating WOFF2 webfonts..."
	rm -rf webfonts
	python3 scripts/generate_webfonts.py
	@touch webfonts.stamp
	@echo "==> WOFF2 webfonts available in webfonts/"

webfonts: webfonts.stamp

# Stage 3: Generate specimen images with DrawBot
images: postprocess.stamp $(DRAWBOT_OUTPUT)

documentation/%.png: documentation/%.py postprocess.stamp
	python3 $< --output $@




# Testing and proofing
test: postprocess.stamp
	which fontspector || (echo "fontspector not found. Please install it with \"cargo install fontspector\"." && exit 1)
	mkdir -p out/fontspector
	fontspector --profile googlefonts -l warn --full-lists --succinct \
		--skip-network \
		-x fontdata_namecheck \
		--html out/fontspector/fontspector-report.html \
		--ghmarkdown out/fontspector/fontspector-report.md \
		--badges out/badges $$(find fonts -type f -name "*.ttf") || \
		echo "::warning file=sources/config.yaml,title=fontspector failures::The fontspector QA check reported errors in your font. Please check the generated report."
# Excluded checks:
# - fontdata_namecheck: requires network access to namecheck.fontdata.com which is
#   unreliable and errors in sandboxed/CI environments.

test-harfbuzz: postprocess.stamp
	@echo "===> Running HarfBuzz mark positioning tests..."
	python3 tests/test_harfbuzz_marks.py

proof: postprocess.stamp
	mkdir -p out/proof
	diffenator2 proof $$(find fonts -type f -name "*.ttf") -o out/proof

compare: postprocess.stamp
	mkdir -p out/compare
	diffenator2 diff \
		--fonts-before $$(find unprocessed_fonts -type f -name "*.ttf") \
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
# Usage: make update-subtree [TAG=v34.0.0]
update-subtree:
	@upstream_url="https://github.com/be5invis/Iosevka.git"; \
	if git remote get-url iosevka-upstream >/dev/null 2>&1; then \
		current_url="$$(git remote get-url iosevka-upstream)"; \
		if [ "$$current_url" != "$$upstream_url" ]; then \
			echo "==> Updating iosevka-upstream remote to $$upstream_url"; \
			git remote set-url iosevka-upstream "$$upstream_url"; \
		fi; \
	else \
		echo "==> Adding iosevka-upstream remote: $$upstream_url"; \
		git remote add iosevka-upstream "$$upstream_url"; \
	fi; \
	tag="$(TAG)"; \
	if [ -z "$$tag" ]; then \
		echo "==> Resolving latest upstream release tag..."; \
		tag="$$(git ls-remote --refs --tags iosevka-upstream 'v*' | awk -F/ '{print $$3}' | sort -V | tail -n 1)"; \
	fi; \
	if [ -z "$$tag" ]; then \
		echo "Error: Could not determine an upstream release tag"; \
		exit 1; \
	fi; \
	echo "==> Updating Iosevka subtree to $$tag..."; \
	git fetch iosevka-upstream tag "$$tag" --no-tags; \
	git subtree pull --prefix=sources/iosevka iosevka-upstream "$$tag" -m "Update Iosevka subtree to $$tag"; \
	echo "==> Subtree updated successfully to $$tag"

.PHONY: $(TEST_TARGETS) help clean update-subtree webfonts sync-version
