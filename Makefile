ENV_RUNNER := ./scripts/run-in-nix.sh
PLAN := sources/private-build-plans.toml
SOURCES := $(shell find sources -type f)

help:
	@echo "###"
	@echo "# Build targets for Iosevka Charon"
	@echo "###"
	@echo
	@echo "  make build:                          Builds the fonts (in Nix)"
	@echo "  make build PLAN=<path-to-toml>:      Builds fonts using a custom build plan"
	@echo "  make test:                           Runs fontspector checks on the built fonts (in Nix)"
	@echo "  make proof:                          Generates HTML proofs via diffenator2 (in Nix)"
	@echo "  make update-deps:                    Updates Python dependencies lockfile"
	@echo "  make clean:                          Removes build artifacts"
	@echo

build: build.stamp

build.stamp: $(SOURCES)
	rm -rf fonts
	$(ENV_RUNNER) bash sources/build.sh "$(PLAN)" && touch build.stamp

test: build.stamp
	$(ENV_RUNNER) bash -c 'which fontspector || (echo "fontspector not found. Please install it with \"cargo install fontspector\"." && exit 1); TOCHECK=$$(find fonts/variable -type f 2>/dev/null); if [ -z "$$TOCHECK" ]; then TOCHECK=$$(find fonts/ttf -type f 2>/dev/null); fi ; mkdir -p out/ out/fontspector; fontspector --profile googlefonts -l warn --full-lists --succinct --html out/fontspector/fontspector-report.html --ghmarkdown out/fontspector/fontspector-report.md --badges out/badges $$TOCHECK || echo "::warning file=sources/config.yaml,title=fontspector failures::The fontspector QA check reported errors in your font. Please check the generated report."'

proof: build.stamp
	$(ENV_RUNNER) bash -c 'TOCHECK=$$(find fonts/variable -type f 2>/dev/null); if [ -z "$$TOCHECK" ]; then TOCHECK=$$(find fonts/ttf -type f 2>/dev/null); fi ; mkdir -p out/ out/proof; diffenator2 proof $$TOCHECK -o out/proof'

update-deps:
	$(ENV_RUNNER) bash sources/scripts/update_all.sh

clean:
	git clean -fdx
