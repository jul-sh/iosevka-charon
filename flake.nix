{
  description = "Iosevka Charon - Custom Iosevka font variant";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    rust-overlay.url = "github:oxalica/rust-overlay";
    rust-overlay.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, flake-utils, rust-overlay }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        overlays = [ (import rust-overlay) ];
        pkgs = import nixpkgs {
          inherit system overlays;
        };

        # Python environment with font processing tools
        pythonEnv = pkgs.python3.withPackages (ps: with ps; [
          # Core font tools
          fonttools
          fontmake
          fontbakery
          glyphslib
          gftools
          ufo2ft
          ufolint
          defcon
          fontmath
          diffenator2

          # Additional font processing dependencies
          brotli
          pillow
          requests
          pyyaml
          jinja2
          rich
          click
          toml
          pygments
          dehinter
          freetype-py
          unicodedata2
          uharfbuzz

          # Additional packages
          setuptools
          pip
        ]);

        # Custom derivation for fontspector (built from main to include fix for #501)
        fontspector = pkgs.rustPlatform.buildRustPackage rec {
          pname = "fontspector";
          version = "1.5.1-git";

          src = pkgs.fetchFromGitHub {
            owner = "fonttools";
            repo = "fontspector";
            rev = "e4722fef242bc3554263a87e2b67599312e4dc14";
            hash = "sha256-s3w+uWvi+S0FP7yi6mCSDhCmJsJCTBK9eFm2NSU3SM0=";
          };

          cargoHash = "sha256-5C/u25SYNAdPjvJ8Lb2s6EBuHR593eYe5Bps5hwiC4s=";

          # Patch to make fontspector-checkapi offline-buildable for Nix sandboxed builds
          patches = [ ./nix/patches/fontspector-offline.patch ];

          # Vendor the generated script_tags.rs and language_tags.rs files
          # to avoid network access during build
          postPatch = ''
            cp ${./nix/patches/fontspector-checkapi-src/script_tags.rs} fontspector-checkapi/src/script_tags.rs
            cp ${./nix/patches/fontspector-checkapi-src/language_tags.rs} fontspector-checkapi/src/language_tags.rs
          '';

          # Build only the CLI binary, not all workspace members
          cargoBuildFlags = [ "-p" "fontspector" ];
          cargoTestFlags = [ "-p" "fontspector" ];

          nativeBuildInputs = with pkgs; [
            pkg-config
          ];

          buildInputs = with pkgs; [
            openssl
            zlib
          ];

          meta = with pkgs.lib; {
            description = "Skrifa/Read-Fonts-based font QA tool (successor to fontbakery)";
            homepage = "https://github.com/fonttools/fontspector";
            license = licenses.asl20;
            maintainers = [ ];
            mainProgram = "fontspector";
          };
        };
      in
      {
        packages.fontspector = fontspector;

        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # Rust toolchain - nightly version
            rust-bin.nightly.latest.default

            # Custom fontspector package
            fontspector

            # Node.js and npm for the Iosevka build system
            nodejs

            # Python environment with all font tools
            pythonEnv

            # Other useful tools
            git
            which
            ttfautohint
          ];

          shellHook = ''
            export PYTHONPATH="${pythonEnv}/${pythonEnv.sitePackages}"
            # Workaround for protobuf compatibility with gflanguages
            export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

            echo "Starting Iosevka Charon development environment..."
            echo "Rust version: $(rustc --version)"
            echo "Node version: $(node --version)"
            echo "Python version: $(python --version)"
            echo "fontspector version: $(fontspector --version)"
            echo "fonttools version: $(python -c 'import fontTools; print(fontTools.__version__)' 2>/dev/null || echo 'check failed')"
            echo "gftools available: $(python -c 'import gftools; print(\"yes\")' 2>/dev/null || echo 'no')"
            echo "Ready to build Iosevka Charon!"
          '';
        };
      });
}
