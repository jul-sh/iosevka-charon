ENV_RUNNER := ./scripts/run-in-nix.sh
FONTS_DIR := fonts/ttf
REPORT_DIR := out/fontbakery
PROOF_DIR := out/proof

help:
	@echo "###"
	@echo "# Build targets for Iosevka Charon"
	@echo "###"
	@echo
	@echo "  make build:  Builds the fonts inside the Nix+uv environment"
	@echo "  make test:   Runs FontBakery checks on the built TTFs"
	@echo "  make proof:  Generates HTML proofs via diffenator2"
	@echo

build:
	$(ENV_RUNNER) bash sources/build.sh

test: build
	$(ENV_RUNNER) bash sources/scripts/check_fonts.sh $(FONTS_DIR) $(REPORT_DIR)

proof: build
	$(ENV_RUNNER) bash -lc 'TTF=$$(find $(FONTS_DIR) -type f -name "*.ttf"); [ -n "$$TTF" ] || { echo "No TTF files found in $(FONTS_DIR)"; exit 1; }; mkdir -p $(PROOF_DIR); gftools gen-html $$TTF --out $(PROOF_DIR)'

update-uv-lock:
	$(ENV_RUNNER) bash sources/scripts/update_uv_lock.sh

clean:
	rm -rf fonts out build.stamp .venv
	find . -name "*.pyc" -delete
