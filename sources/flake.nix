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

            # Pin versions for compatibility
            # Run 'make update-deps' to update to latest versions
            RUST_VERSION="nightly-2025-11-30"
            FONTSPECTOR_VERSION="1.5.1"

            # Install Rust toolchain if not already installed
            if ! rustup show &> /dev/null; then
              echo "Setting up Rust toolchain $RUST_VERSION..."
              rustup-init -y --default-toolchain "$RUST_VERSION" --profile minimal
            else
              # Ensure the pinned version is installed
              CURRENT_TOOLCHAIN=$(rustup show active-toolchain 2>/dev/null | awk '{print $1}' || echo "")
              if [ "$CURRENT_TOOLCHAIN" != "$RUST_VERSION" ]; then
                if ! rustup toolchain list | grep -q "$RUST_VERSION"; then
                  echo "Installing Rust $RUST_VERSION..."
                  rustup toolchain install "$RUST_VERSION" --profile minimal
                fi
                echo "Setting Rust $RUST_VERSION as default..."
                rustup default "$RUST_VERSION"
              fi
            fi

            # Install fontspector at pinned version if not already installed (optional, best-effort)
            if ! command -v fontspector &> /dev/null; then
              echo "Installing fontspector $FONTSPECTOR_VERSION..."
              if ! cargo install fontspector --version "$FONTSPECTOR_VERSION" 2>&1; then
                echo "⚠ Warning: fontspector $FONTSPECTOR_VERSION failed to install."
                echo "  This is optional. You can manually install with: cargo install fontspector"
              fi
            elif ! fontspector --version 2>&1 | grep -q "$FONTSPECTOR_VERSION"; then
              echo "Updating fontspector to $FONTSPECTOR_VERSION..."
              if ! cargo install fontspector --version "$FONTSPECTOR_VERSION" --force 2>&1; then
                echo "⚠ Warning: fontspector $FONTSPECTOR_VERSION failed to install."
                echo "  Current version: $(fontspector --version 2>&1 || echo 'none')"
              fi
            fi
          '';
        };
      });
}
