# Font Testing Scripts

This directory contains standalone test scripts that can be run locally or in CI.

## Quick Start

Run all tests:
```bash
./tests/run-all.sh
```

Run individual tests:
```bash
./tests/validate-environment.sh  # Check Nix flake and dependencies
./tests/build-fonts.sh          # Build fonts
./tests/test-fonts.sh           # Run quality tests with fontspector
./tests/generate-proofs.sh      # Generate proof documents
```

## Requirements

- Nix with flakes enabled
- All tests should be run from the project root directory

## Test Scripts

### `validate-environment.sh`
Validates the Nix environment and ensures all required tools are available:
- Checks `nix flake check` passes
- Verifies fontspector builds successfully
- Validates development shell has required tools (Rust, Node, Python, fontspector, diffenator2)

**Exit codes:**
- `0` - All validations passed
- `1` - Validation failed

### `build-fonts.sh`
Builds the fonts and verifies output:
- Runs `make build`
- Checks that TTF files were generated
- Lists all generated font files

**Exit codes:**
- `0` - Fonts built successfully
- `1` - Build failed or no fonts generated

### `test-fonts.sh`
Runs fontspector quality tests:
- Executes `make test`
- Generates test report in `out/fontspector/`
- Displays test summary
- **Fails if fontspector reports issues**

**Exit codes:**
- `0` - All tests passed
- `1` - Tests failed (fonts may have quality issues)

**Outputs:**
- `out/fontspector/fontspector-report.md` - Markdown test report
- `out/fontspector/fontspector-report.html` - HTML test report

### `generate-proofs.sh`
Generates proof documents:
- Executes `make proof`
- Creates HTML proof documents in `out/proof/`
- Lists all generated proof files

**Exit codes:**
- `0` - Proofs generated successfully
- `1` - Proof generation failed

**Outputs:**
- `out/proof/diffenator2-report.html` - Main proof report
- `out/proof/*-diffbrowsers_*.html` - Individual style proofs

### `run-all.sh`
Orchestrates the complete test suite:
- Runs all tests in sequence
- Provides clear progress indication
- Shows summary of passed/failed tests
- Continues on non-critical failures (environment, proofs)
- Stops on critical failures (build, tests)

**Exit codes:**
- `0` - All tests passed
- `1` - One or more tests failed

## Integration with CI

The GitHub Actions workflow (`.github/workflows/build.yaml`) uses these same scripts, ensuring that what runs in CI is identical to what developers run locally.

## Tips

- Run `./tests/build-fonts.sh` once, then iterate on `./tests/test-fonts.sh` for faster feedback
- Use `./tests/validate-environment.sh` when setting up a new development environment
- Generate proofs with `./tests/generate-proofs.sh` to preview fonts before release
- The test reports in `out/fontspector/` provide detailed information about any issues

## Troubleshooting

**"No fonts found" error:**
```bash
# Build fonts first
./tests/build-fonts.sh
```

**Nix flake check fails:**
```bash
# Try updating flake inputs
nix flake update
```

**fontspector build fails:**
```bash
# Check the vendored patch files exist
ls -la nix/patches/fontspector-*
```
