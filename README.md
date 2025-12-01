# Iosevka Charon

Iosevka Charon is a quasi-proportional font excellent for technical writing and dense UI. Iosevka Charon Mono is a true monospace font tuned for coding and terminal use. This repository builds each family from scratch and publishes TTFs with every release. Its unique contribution is that it takes the upstream [Iosevka](https://github.com/be5invis/Iosevka) source code by **Belleve Invis** and builds it in a way that makes the resulting fonts Google Fonts compliant.

## Building and testing

The Make targets rely on the Nix flake dev shell, which not only bootstraps uv and the Python venv but also supplies the native toolchain required to build the fonts (e.g., Node, ttfautohint, and Git). If Nix is installed, `make` automatically enters the flake dev shell; when Nix is absent but Docker is available, the same flow runs inside the official `nixos/nix` container. With either tool installed, you can rely solely on the standard GNU Make entry points:

- `make build` – enter the Nix shell, build the fonts, and output TTFs to `fonts/`.
- `make fonts` – build raw fonts only (stage 1: Iosevka sources → `sources/output/`).
- `make postprocess` – post-process fonts only (stage 2: `sources/output/` → `fonts/` with Google Fonts compliance fixes).
- `make test` – run fontspector against the built TTFs, writing reports to `out/fontspector`.
- `make proof` – generate diffenator2 HTML proofs in `out/proof` using the built TTFs.

The build process is split into two stages with individual stamp files (`fonts.stamp`, `postprocess.stamp`):
1. **Build raw fonts** (`sources/output/`) – builds fonts from Iosevka sources without modifications
2. **Post-process** (`fonts/`) – applies Google Fonts compliance fixes and outputs final fonts with proper naming

This allows you to re-run just the post-processing step if you modify those scripts, without rebuilding fonts from scratch.

## Tooling

- Nix flake in `flake.nix` (root) provisions Node, uv, native build tools (like ttfautohint), and other supporting dependencies.
- uv syncs Python dependencies and activates `.venv` automatically via the flake `shellHook`.
- `sources/iosevka` is a git subtree containing the upstream Iosevka sources.
- `sources/scripts/` contains build scripts for raw font generation.
- `scripts/` contains post-processing scripts for Google Fonts compliance.

## Repository layout

- `sources/` – Iosevka subtree, build plans, and build scripts for raw fonts → `sources/output/`
- `scripts/` – post-processing scripts that transform `sources/output/` → `fonts/`
- `fonts/` – final TTFs created by `make build` (gitignored)
- `out/` – QA reports and proofs from `make test` / `make proof` (gitignored)
- `documentation/` – specimen assets (from the Google Fonts template)
- `flake.nix` – Nix development environment configuration

## License

SIL Open Font License 1.1 (see `OFL.txt`).
