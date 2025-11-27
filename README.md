# Iosevka Charon

Iosevka Charon is a quasi-proportional font excellent for technical writing and dense UI. Iosevka Charon Mono is a true monospace font tuned for coding and terminal use. This repository builds each family from scratch and publishes TTFs with every release. Its unique contribution is that it takes the upstream [Iosevka](https://github.com/be5invis/Iosevka) source code by **Belleve Invis** and builds it in a way that makes the resulting fonts Google Fonts compliant.

## Building and testing

The Make targets rely on the Nix flake dev shell, which not only bootstraps uv and the Python venv but also supplies the native toolchain required to build the fonts (e.g., Node, ttfautohint, and Git). If Nix is installed, `make` automatically enters the flake dev shell; when Nix is absent but Docker is available, the same flow runs inside the official `nixos/nix` container. With either tool installed, you can rely solely on the standard GNU Make entry points:

- `make build` – enter the Nix shell, sync the Iosevka submodule, build the fonts, and copy TTFs to `fonts/ttf/…`.
- `make test` – run FontBakery (with the Beria Erfe script patch) against the built TTFs, writing reports to `out/fontbakery`.
- `make proof` – generate diffenator2 HTML proofs in `out/proof` using the built TTFs.

## Tooling

- Nix flake in `sources/flake.nix` provisions Node, uv, native build tools (like ttfautohint), and other supporting dependencies.
- uv syncs Python dependencies from `sources/requirements.lock` and activates `.venv` automatically via the flake `shellHook`.
- `sources/iosevka` is a submodule tracking the upstream gf branch of the Iosevka sources.

## Repository layout

- `sources/` – build scripts, Nix flake, uv lockfile, build plans, and the Iosevka submodule.
- `fonts/` – output TTFs created by `make build` (gitignored).
- `out/` – QA reports and proofs from `make test` / `make proof` (gitignored).
- `documentation/` – specimen assets (from the Google Fonts template).

## License

SIL Open Font License 1.1 (see `OFL.txt`).
