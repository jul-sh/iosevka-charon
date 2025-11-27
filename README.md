# Iosevka Charon

Custom Google Fonts–compliant repository for the Iosevka Charon and Iosevka Charon Mono builds. This project keeps the Google Fonts template layout while using the repository's Nix + uv toolchain, and stays aligned with Google Fonts repository expectations.

## Building and testing

The Make targets wrap the Nix flake dev shell (which bootstraps uv and the Python venv) and the Iosevka build scripts. If Nix is installed, `make` automatically enters the flake dev shell; when Nix is absent but Docker is available, the same flow runs inside the official `nixos/nix` container. With either tool installed, you can rely solely on the standard GNU Make entry points:

- `make build` – enter the Nix shell, sync the Iosevka submodule, build the fonts, and copy TTFs to `fonts/ttf/…`.
- `make test` – run FontBakery (with the Beria Erfe script patch) against the built TTFs, writing reports to `out/fontbakery`.
- `make proof` – generate diffenator2 HTML proofs in `out/proof` using the built TTFs.

## Tooling

- Nix flake in `sources/flake.nix` provisions Node, uv, and supporting tools.
- uv syncs Python dependencies from `sources/requirements.lock` and activates `.venv` automatically via the flake `shellHook`.
- `sources/iosevka` is a submodule tracking the upstream gf branch of the Iosevka sources.

## Repository layout

- `sources/` – build scripts, Nix flake, uv lockfile, build plans, and the Iosevka submodule.
- `fonts/` – output TTFs created by `make build` (gitignored).
- `out/` – QA reports and proofs from `make test` / `make proof` (gitignored).
- `documentation/` – specimen assets (from the Google Fonts template).

## License

SIL Open Font License 1.1 (see `OFL.txt`).
