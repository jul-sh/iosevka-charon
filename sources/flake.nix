{
  description = "Font development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            ttfautohint
            nodejs
            uv
            git
          ];

          shellHook = ''
            # Set up uv virtual environment
            readonly REPO_ROOT="$(git rev-parse --show-toplevel)"
            readonly VENV_DIR="$(git rev-parse --show-toplevel)/.venv"
            readonly REQUIREMENTS="$(git rev-parse --show-toplevel)/sources/requirements.txt"
            readonly UV_LOCKFILE="$(git rev-parse --show-toplevel)/sources/requirements.lock"

            uv venv "$VENV_DIR"
            uv pip sync "$UV_LOCKFILE"
            source "$VENV_DIR/bin/activate"
          '';
        };
      });
}
