ENV_RUNNER := ./scripts/run-in-nix.sh
FONTS_DIR := fonts/ttf
REPORT_DIR := out/fontbakery
PROOF_DIR := out/proof
PLAN := sources/private-build-plans.toml

help:
	@echo "###"
	@echo "# Build targets for Iosevka Charon"
	@echo "###"
	@echo
	@echo "  make build:                          Builds the fonts inside the Nix+uv environment"
	@echo "  make build PLAN=<path-to-toml>:      Builds fonts using a custom build plan"
	@echo "  make test:                           Runs FontBakery checks on the built TTFs"
	@echo "  make proof:                          Generates HTML proofs via diffenator2"
	@echo
	@echo "Examples:"
	@echo "  make build                                    # Use default build plan"
	@echo "  make build PLAN=sources/test-build-plans.toml # Use test build plan"
	@echo

build:
	$(ENV_RUNNER) bash sources/build.sh "$(PLAN)"

test: build
	$(ENV_RUNNER) bash sources/scripts/check_fonts.sh $(FONTS_DIR) $(REPORT_DIR)

proof: build
	$(ENV_RUNNER) bash -lc 'TTF=$$(find $(FONTS_DIR) -type f -name "*.ttf"); [ -n "$$TTF" ] || { echo "No TTF files found in $(FONTS_DIR)"; exit 1; }; mkdir -p $(PROOF_DIR); gftools gen-html proof $$TTF --out $(PROOF_DIR)'

update-uv-lock:
	$(ENV_RUNNER) bash sources/scripts/update_uv_lock.sh

clean:
	rm -rf fonts out build.stamp .venv
	find . -name "*.pyc" -delete
