# Nix Shell Usage for Iosevka Charon

## Important: Always Use Nix Shell

This project uses a Nix development environment that provides all necessary build tools and dependencies. **Always use the Makefile targets** which automatically invoke the Nix shell - do NOT try to run commands directly.

## Why Use the Nix Shell?

The Nix environment (`flake.nix`) provides:
- Node.js
- Python with all font processing packages (fonttools, fontmake, fontbakery, gftools, etc.)
- Rust/Cargo (for fontspector)
- ttfautohint
- fontspector
- All other build dependencies

## How It Works

The `ENV_RUNNER` variable in the Makefile points to `./scripts/run-in-nix.sh`, which:
1. Checks for Nix installation
2. Falls back to Docker with nixos/nix image if Nix not installed
3. Automatically enters the development shell
4. Runs your command with all dependencies available

## Correct Usage

### ✅ DO THIS - Use Make targets:
```bash
make build          # Build fonts
make test           # Run fontspector
make proof          # Generate HTML proofs
make clean          # Clean build artifacts
```

### ❌ DON'T DO THIS - Direct commands:
```bash
python scripts/build_fonts.py              # Won't work - missing deps
fontspector --profile googlefonts ...      # Won't work - not installed
npm run build -- ttf::IosevkaCharon        # Won't work - wrong environment
```

## Available Make Targets

| Target | Description |
|--------|-------------|
| `make build` | Full build pipeline (fonts → post-processing) |
| `make fonts` | Stage 1: Build raw fonts only |
| `make postprocess` | Stage 2: Post-process for Google Fonts compliance |
| `make test` | Run fontspector QA checks |
| `make proof` | Generate HTML font proofs |
| `make images` | Generate specimen images with DrawBot |
| `make clean` | Remove build artifacts |

## Test Results Location

After running `make test`:
- **HTML Report**: `out/fontspector/fontspector-report.html` (open in browser)
- **Markdown Report**: `out/fontspector/fontspector-report.md`
- **Badge Output**: `out/badges/`

## For Claude/AI Agents

When the user asks to:
- "Build fonts" → Use `make build`
- "Run tests" → Use `make test`
- "Check font quality" → Use `make test` then read reports
- "Generate proofs" → Use `make proof`

**Never** attempt to run Python scripts, npm commands, or fontspector directly. Always use the Makefile, which handles the Nix environment automatically.
