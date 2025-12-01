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
            python312
            ttfautohint
            nodejs
            uv
            git
            rustup
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

            # Set up Rust toolchain
            export RUSTUP_HOME="$HOME/.rustup"
            export CARGO_HOME="$HOME/.cargo"
            export PATH="$CARGO_HOME/bin:$PATH"

            # Install latest stable Rust if not already installed
            if ! rustup show &> /dev/null; then
              echo "Setting up Rust toolchain..."
              rustup-init -y --default-toolchain stable --profile minimal
            fi

            # Install fontspector if not already installed
            if ! command -v fontspector &> /dev/null; then
              echo "Installing fontspector..."
              cargo install fontspector
            fi
          '';
        };
      });
}
