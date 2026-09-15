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

        # crates.io's bot protection answers requests that carry no User-Agent
        # with HTTP 403, and nixpkgs' fetch-cargo-vendor-util builds a bare
        # requests.Session that sets none, so every buildRustPackage vendor
        # fetch fails. The util is constructed inline inside
        # fetch-cargo-vendor.nix rather than exposed as a package, so it cannot
        # be reached from an overlay; patch the nixpkgs source instead.
        # Remove once nixpkgs sends a User-Agent itself.
        # A module-level helper, emitted with explicit "\n" joins so neither
        # Nix's indented-string stripping nor bash quoting can disturb the
        # Python indentation.
        userAgentHelper = builtins.concatStringsSep "\n" [
          "def _session_with_user_agent() -> requests.Session:"
          "    session = requests.Session()"
          "    session.headers.update("
          "        {'User-Agent': 'nix-fetch-cargo-vendor (+https://github.com/NixOS/nixpkgs)'}"
          "    )"
          "    return session"
          ""
          ""
          ""
        ];

        # Split across lines to stay within flake8's 79-column limit (E501).
        retryPolicy = builtins.concatStringsSep "\n" [
          "        status_forcelist=[429, 500, 502, 503, 504],"
          "        respect_retry_after_header=True,"
        ];

        patchedNixpkgs = pkgsBootstrap.applyPatches {
          name = "nixpkgs-crates-io-user-agent";
          src = nixpkgs;
          # Substitute the Session constructor for one that carries a
          # User-Agent. It has to stay a single statement on a single line:
          # a multi-line replacement would have to survive both Nix's
          # indented-string stripping and bash quoting (losing the leading
          # spaces gives a Python IndentationError), and writePython3Bin
          # lints the result with flake8, which rejects a semicolon (E702).
          # requests.Session accepts no headers argument, so build it with a
          # dict literal merge inside a helper expression instead.
          postPatch = ''
            substituteInPlace pkgs/build-support/rust/fetch-cargo-vendor-util.py \
              --replace-fail \
                "    session = requests.Session()" \
                "    session = _session_with_user_agent()"

            substituteInPlace pkgs/build-support/rust/fetch-cargo-vendor-util.py \
              --replace-fail \
                "def create_http_session() -> requests.Session:" \
                "${userAgentHelper}def create_http_session() -> requests.Session:"

            # crates.io also throttles the fetcher's parallel download pool
            # with HTTP 429, which upstream's retry policy does not cover
            # (it retries 5xx only), so a large vendor fetch fails outright.
            # Retry on 429 as well, and back off harder.
            substituteInPlace pkgs/build-support/rust/fetch-cargo-vendor-util.py \
              --replace-fail \
                "        status_forcelist=[500, 502, 503, 504]" \
                "${retryPolicy}"

            substituteInPlace pkgs/build-support/rust/fetch-cargo-vendor-util.py \
              --replace-fail \
                "        backoff_factor=0.5," \
                "        backoff_factor=2.0,"

            substituteInPlace pkgs/build-support/rust/fetch-cargo-vendor-util.py \
              --replace-fail \
                "        total=5," \
                "        total=10,"
          '';
        };

        pkgsBootstrap = import nixpkgs { inherit system; };

        pkgs = import patchedNixpkgs {
          inherit system overlays;
        };

        # Custom Python packages not in nixpkgs
        tricycle = pkgs.python3Packages.buildPythonPackage rec {
          pname = "tricycle";
          version = "0.4.1";
          src = pkgs.python3Packages.fetchPypi {
            inherit pname version;
            hash = "sha256-9W7bSz4b7T4lUrG0mbJKLatHdB6S6bTYBqzFw1yeYGY=";
          };
          format = "pyproject";
          nativeBuildInputs = [ pkgs.python3Packages.setuptools ];
          propagatedBuildInputs = [ pkgs.python3Packages.trio ];
          doCheck = false;
        };

        trio-parallel = pkgs.python3Packages.buildPythonPackage rec {
          pname = "trio-parallel";
          version = "1.3.0";
          src = pkgs.python3Packages.fetchPypi {
            pname = "trio_parallel";
            inherit version;
            hash = "sha256-2xJCoZI4g84VURRlyY8vQ31rxpWWsa/i79l4LvE4cQc=";
          };
          format = "pyproject";
          nativeBuildInputs = with pkgs.python3Packages; [ setuptools setuptools-scm ];
          propagatedBuildInputs = with pkgs.python3Packages; [
            trio
            outcome
            attrs
            tblib
            tricycle
          ];
          doCheck = false;
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

          # Auto-kerning (HalfKern) dependencies
          pycairo
          numpy
          scipy
          scikit-fmm

          # Async concurrency
          trio
          outcome
          trio-parallel
          tricycle

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

            # System libraries needed by HalfKern (cairoft.py dlopen)
            cairo
            freetype

            # Other useful tools
            git
            which
            ttfautohint
          ];

          shellHook = ''
            export PYTHONPATH="${pythonEnv}/${pythonEnv.sitePackages}"
            # Make native libs findable by HalfKern's cairoft.py (ctypes.CDLL)
            export DYLD_FALLBACK_LIBRARY_PATH="${pkgs.cairo}/lib:${pkgs.freetype}/lib:''${DYLD_FALLBACK_LIBRARY_PATH:-}"
            export LD_LIBRARY_PATH="${pkgs.cairo}/lib:${pkgs.freetype}/lib:''${LD_LIBRARY_PATH:-}"
            # Workaround for protobuf compatibility with gflanguages
            export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
            # Install trio-parallel (not available in nixpkgs)
            pip install --quiet --user trio-parallel 2>/dev/null || true
          '';
        };
      });
}
