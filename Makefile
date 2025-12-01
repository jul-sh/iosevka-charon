ENV_RUNNER := ./scripts/run-in-nix.sh
PLAN := sources/private-build-plans.toml

# Source dependencies for each stage
BUILD_SOURCES := $(PLAN) $(shell find sources/iosevka -type f 2>/dev/null) $(shell find sources/scripts -name "build_fonts.py" 2>/dev/null)
POSTPROCESS_SOURCES := $(shell find scripts -name "post_process*.py" -o -name "fix_fonts.py" 2>/dev/null)

help:
	@echo "###"
	@echo "# Build targets for Iosevka Charon"
	@echo "###"
	@echo
	@echo "  make build:                          Builds the fonts (all stages, in Nix)"
	@echo "  make build PLAN=<path-to-toml>:      Builds fonts using a custom build plan"
	@echo "  make fonts:                          Builds raw fonts only (stage 1: sources → sources/output/)"
	@echo "  make postprocess:                    Post-processes fonts (stage 2: sources/output/ → fonts/)"
	@echo "  make test:                           Runs fontspector checks on the built fonts (in Nix)"
	@echo "  make proof:                          Generates HTML proofs via diffenator2 (in Nix)"
	@echo "  make clean:                          Removes build artifacts and stamp files"
	@echo

# Full build pipeline
build: postprocess.stamp

# Stage 1: Build raw fonts from Iosevka, into sources/output
fonts.stamp: $(BUILD_SOURCES)
	@echo "==> Stage 1: Building raw fonts from Iosevka sources..."
	@echo "Using build plan: $(PLAN)"
	$(ENV_RUNNER) python3 sources/scripts/build_fonts.py "$(PLAN)"
	@touch fonts.stamp
	@echo "==> Raw fonts built successfully in sources/output/"

fonts: fonts.stamp

# Stage 2: Post-process fonts for Google Fonts compliance and output to fonts/
postprocess.stamp: fonts.stamp $(POSTPROCESS_SOURCES)
	@echo "==> Stage 2: Post-processing fonts for GF compliance..."
	rm -rf fonts
	$(ENV_RUNNER) python3 scripts/post_process_parallel.py
	@touch postprocess.stamp
	@echo "==> Final fonts available in fonts/"

postprocess: postprocess.stamp

# Testing and proofing
test: postprocess.stamp
	$(ENV_RUNNER) bash -c 'which fontspector || (echo "fontspector not found. Please install it with \"cargo install fontspector\"." && exit 1); \
		TOCHECK=$$(find fonts -type f -name "*.ttf" 2>/dev/null); \
		mkdir -p out/fontspector; \
		fontspector --profile googlefonts -l fail --full-lists --succinct \
			--html out/fontspector/fontspector-report.html \
			--ghmarkdown out/fontspector/fontspector-report.md \
			--badges out/badges $$TOCHECK || \
		echo "::warning file=sources/config.yaml,title=fontspector failures::The fontspector QA check reported errors in your font. Please check the generated report."'

proof: postprocess.stamp
	$(ENV_RUNNER) bash -c 'TOCHECK=$$(find fonts -type f -name "*.ttf" 2>/dev/null); \
		mkdir -p out/proof; \
		diffenator2 proof $$TOCHECK -o out/proof'

clean:
	rm -f fonts.stamp postprocess.stamp
	git stash && git clean -fdx && git stash pop

.PHONY: help build fonts postprocess test proof clean
