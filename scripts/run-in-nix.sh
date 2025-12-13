#!/usr/bin/env bash
#
# Run a command inside the Nix development environment.
# Fallback order:
#   1) host nix
#   2) docker (nixos/nix)
#   3) rootless nix-user-chroot bootstrap (requires user namespaces + cargo)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}${ROOT_DIR}"

log() { echo "[$(basename "$0")] $*" >&2; }
die() { log "ERROR: $*"; exit 1; }

# Handle standard SHELL interface: -c "command"
if [[ "${1:-}" == "-c" ]]; then
  shift
  set -- bash -c "$@"
fi

# If we're already inside a nix shell/dev env, just run.
if [[ -n "${IN_NIX_SHELL:-}" ]]; then
  exec "$@"
fi

NIX_FLAKE="${NIX_FLAKE:-$ROOT_DIR#default}"
NIX_EXPERIMENTAL="${NIX_EXPERIMENTAL:-nix-command flakes}"

run_with_host_nix() {
  exec nix develop --experimental-features "$NIX_EXPERIMENTAL" \
    "$NIX_FLAKE" --command "$ROOT_DIR/scripts/run-in-nix.sh" "$@"
}

run_with_docker() {
  exec docker run --rm -v "$ROOT_DIR:/app" -w /app nixos/nix \
    nix develop --experimental-features "$NIX_EXPERIMENTAL" \
    ".#default" --command /app/scripts/run-in-nix.sh "$@"
}

run_with_user_chroot() {
  # 0) Require user namespaces
  if ! unshare --user --pid bash -lc 'echo YES' >/dev/null 2>&1; then
    die "user namespaces not available (unshare --user --pid failed); cannot use nix-user-chroot fallback"
  fi

  # 1) Require cargo to build nix-user-chroot
  command -v cargo >/dev/null 2>&1 || die "cargo not found; cannot build nix-user-chroot fallback"

  # 2) Workspace-local installs and state (cache these paths in CI if you can)
  CACHE_DIR="${NIX_CHROOT_CACHE_DIR:-$ROOT_DIR/.cache}"
  CARGO_ROOT="${NIX_CHROOT_CARGO_ROOT:-$CACHE_DIR/cargo}"
  CHROOT_ROOT="${NIX_CHROOT_ROOT:-$CACHE_DIR/nix-chroot}"
  CHROOT_HOME="${NIX_CHROOT_HOME:-$CACHE_DIR/nix-home}"

  mkdir -p "$CARGO_ROOT" "$CHROOT_ROOT" "$CHROOT_HOME"

  # Nix installer needs xz to unpack the tarball on most distros
  command -v xz >/dev/null 2>&1 || die "xz not found (install xz-utils/xz); nix installer will fail without it"

  # 3) Ensure nix-user-chroot exists (install locally via cargo)
  export PATH="$CARGO_ROOT/bin:$PATH"
  if ! command -v nix-user-chroot >/dev/null 2>&1; then
    local nuc_ver="${NIX_USER_CHROOT_VERSION:-1.2.2}"
    log "building nix-user-chroot (cargo install) into $CARGO_ROOT ..."
    cargo install --root "$CARGO_ROOT" "nix-user-chroot@${nuc_ver}"
  fi

  # 4) Install Nix inside the chroot if missing
  local nix_bin_host_path="$CHROOT_ROOT/nix/var/nix/profiles/default/bin/nix"
  if [[ ! -x "$nix_bin_host_path" ]]; then
    log "bootstrapping nix inside user chroot at $CHROOT_ROOT ..."
    nix-user-chroot "$CHROOT_ROOT" bash -lc '
      set -euo pipefail
      export HOME="'"$CHROOT_HOME"'"
      mkdir -p "$HOME"
      curl -L https://nixos.org/nix/install | sh -s -- --no-daemon --yes --no-modify-profile --no-channel-add
    '
  fi

  # 5) Run nix develop inside the chroot
  # nix-user-chroot uses /nix/etc/nix (not /etc/nix); set NIX_CONF_DIR explicitly.
  exec nix-user-chroot "$CHROOT_ROOT" bash -lc '
    set -euo pipefail
    export HOME="'"$CHROOT_HOME"'"
    export NIX_CONF_DIR=/nix/etc/nix
    # Ensure nix is on PATH for this non-interactive shell
    . /nix/etc/profile.d/nix.sh
    exec nix develop --experimental-features "'"$NIX_EXPERIMENTAL"'" "'"$NIX_FLAKE"'" --command "$1" "${@:2}"
  ' run-in-chroot "$ROOT_DIR/scripts/run-in-nix.sh" "$@"
}

if command -v nix >/dev/null 2>&1; then
  run_with_host_nix "$@"
fi

log "Nix is not available."
if command -v docker >/dev/null 2>&1; then
  log "Attempting Docker fallback (nixos/nix)."
  run_with_docker "$@"
fi

log "Docker is not available; attempting nix-user-chroot bootstrap fallback."
run_with_user_chroot "$@"
