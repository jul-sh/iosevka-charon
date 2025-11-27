# Iosevka Charon

Custom Google Fonts–style repository for the Iosevka Charon and Iosevka Charon Mono builds. This project keeps the Google Fonts template layout while using the original Nix + uv toolchain from `iosevka-julsh`.

## Building and testing

The Make targets wrap the Nix flake dev shell (which bootstraps uv and the Python venv) and the Iosevka build scripts:

- `make build` – enter the Nix shell, sync the Iosevka submodule, build the fonts, and copy TTFs to `fonts/ttf/…`.
- `make test` – run FontBakery (with the Beria Erfe script patch) against the built TTFs, writing reports to `out/fontbakery`.
- `make proof` – generate diffenator2 HTML proofs in `out/proof` using the built TTFs.

You can also run any command inside the dev shell manually via `./scripts/run-in-nix.sh <command>`.

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
