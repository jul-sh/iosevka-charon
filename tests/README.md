# Font Testing Scripts

This directory contains standalone test scripts that can be run locally or in CI.

## Quick Start

Run all tests:
```bash
./tests/run-all.sh
```

This will run all make targets in sequence:
- `make build` - Build fonts
- `make test` - Run quality tests with fontspector
- `make proof` - Generate proof documents

## Individual Tests

You can also run make targets directly from the project root:

```bash
make build    # Build fonts
make test     # Run fontspector quality tests
make proof    # Generate proof documents
make clean    # Remove build artifacts
```

## Requirements

- Nix with flakes enabled
- All tests should be run from the project root directory

## Test Scripts

### `validate-environment.sh`
Validates the Nix environment:
- Checks `nix flake check` passes

**Exit codes:**
- `0` - Validation passed
- `1` - Validation failed

### `run-all.sh`
Orchestrates the complete test suite:
- Runs all make targets in sequence (`build`, `test`, `proof`)
- Provides clear progress indication
- Shows summary of passed/failed tests
- Stops on build failures, continues on test/proof failures

**Exit codes:**
- `0` - All tests passed
- `1` - One or more tests failed

## Integration with CI

The GitHub Actions workflow (`.github/workflows/build.yaml`) calls make targets directly, ensuring that what runs in CI is identical to what developers run locally.

## Tips

- Run `make build` once, then iterate on `make test` for faster feedback
- Use `./tests/validate-environment.sh` when setting up a new development environment
- Generate proofs with `make proof` to preview fonts before release
- The test reports in `out/fontspector/` provide detailed information about any issues

## Troubleshooting

**"No fonts found" error:**
```bash
# Build fonts first
make build
```

**Nix flake check fails:**
```bash
# Try updating flake inputs
nix flake update
```

**Make targets fail:**
```bash
# Check that you're running from the project root
cd /path/to/iosevka-charon
./tests/run-all.sh
```
