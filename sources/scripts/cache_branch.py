#!/usr/bin/env python3
"""
Utilities for caching build artifacts on a dedicated Git branch.

This script provides three operations:

* ``hash``: print a stable hash derived from the ``sources`` directory tree.
* ``restore``: restore cached artifacts for the given stage and hash.
* ``store``: archive build outputs and commit them to the cache branch.

Caching stages
--------------
``initial``
    Raw build outputs before post-processing (``sources/output``).
``post``
    Post-processed outputs ready for consumption (``fonts/`` and ``sources/output``).

Artifacts are stored on the branch defined by the ``CACHE_BRANCH`` environment
variable (default: ``cache``). The branch is checked out in a separate worktree
at ``.cache/cache-branch`` to avoid polluting the main working directory.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

CACHE_WORKTREE_ROOT = Path(".cache")
DEFAULT_CACHE_BRANCH = "cache"
SOURCES_DIR = "sources"


class CacheError(RuntimeError):
    """Raised when cache operations fail."""


@dataclass
class CacheManager:
    repo_root: Path
    cache_branch: str
    worktree_path: Path

    @classmethod
    def create(cls) -> "CacheManager":
        repo_root = Path(
            subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True)
            .strip()
        )
        cache_branch = os.environ.get("CACHE_BRANCH", DEFAULT_CACHE_BRANCH)
        worktree_path = repo_root / CACHE_WORKTREE_ROOT / "cache-branch"
        return cls(repo_root=repo_root, cache_branch=cache_branch, worktree_path=worktree_path)

    # Git helpers ---------------------------------------------------------
    def _run_git(self, args: List[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=cwd or self.repo_root,
            check=check,
            text=True,
            capture_output=True,
        )

    def _branch_exists(self) -> bool:
        result = self._run_git(
            ["show-ref", "--verify", f"refs/heads/{self.cache_branch}"], check=False
        )
        return result.returncode == 0

    def _worktree_present(self) -> bool:
        result = self._run_git(["worktree", "list", "--porcelain"])
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                path = Path(line.split(" ", 1)[1]).resolve()
                if path == self.worktree_path.resolve():
                    return True
        return False

    def _ensure_cache_branch(self) -> None:
        if self._branch_exists():
            return

        empty_tree = (
            self._run_git(["hash-object", "-t", "tree", "/dev/null"])
            .stdout.strip()
        )
        empty_commit = (
            self._run_git(["commit-tree", empty_tree, "-m", "Initialize cache branch"])
            .stdout.strip()
        )
        self._run_git(["branch", self.cache_branch, empty_commit])

    def _ensure_worktree(self) -> None:
        self._ensure_cache_branch()
        self.worktree_path.parent.mkdir(parents=True, exist_ok=True)

        if not self._worktree_present():
            self._run_git(["worktree", "add", "-f", str(self.worktree_path), self.cache_branch])

        # Best-effort update from origin if present.
        remotes = self._run_git(["remote"], check=False)
        if "origin" in remotes.stdout.split():
            self._run_git(["-C", str(self.worktree_path), "fetch", "origin", self.cache_branch], check=False)
            self._run_git(
                ["-C", str(self.worktree_path), "merge", "--ff-only", f"origin/{self.cache_branch}"],
                check=False,
            )

    # Artifact handling ---------------------------------------------------
    def compute_source_hash(self) -> str:
        try:
            return (
                self._run_git(["rev-parse", f"HEAD:{SOURCES_DIR}"], check=True)
                .stdout.strip()
            )
        except subprocess.CalledProcessError as exc:
            raise CacheError(
                f"Unable to compute source hash from '{SOURCES_DIR}': {exc.stderr.strip()}"
            ) from exc

    def artifact_path(self, source_hash: str, stage: str) -> Path:
        if stage not in {"initial", "post"}:
            raise CacheError(f"Unknown cache stage '{stage}'")
        return self.worktree_path / "artifacts" / source_hash / f"{stage}.tar.gz"

    def _clean_stage_destinations(self, stage: str) -> None:
        targets = [self.repo_root / SOURCES_DIR / "output"]
        if stage == "post":
            targets.append(self.repo_root / "fonts")

        for target in targets:
            if target.exists():
                if target.is_dir():
                    for child in target.iterdir():
                        if child.is_dir():
                            shutil.rmtree(child)
                        else:
                            child.unlink()
                else:
                    target.unlink()

    def restore(self, source_hash: str, stage: str) -> bool:
        self._ensure_worktree()
        archive = self.artifact_path(source_hash, stage)
        if not archive.exists():
            return False

        print(f"Restoring {stage} artifacts from cache for {source_hash}…")
        self._clean_stage_destinations(stage)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(self.repo_root)
        return True

    def _assert_paths_exist(self, paths: Iterable[Path]) -> None:
        missing = [path for path in paths if not path.exists()]
        if missing:
            display = ", ".join(str(path) for path in missing)
            raise CacheError(f"Cannot cache missing paths: {display}")

    def store(self, source_hash: str, stage: str, rel_paths: List[str]) -> bool:
        self._ensure_worktree()
        archive = self.artifact_path(source_hash, stage)
        if archive.exists():
            print(f"Cache hit for {stage} artifacts ({source_hash}); skipping upload.")
            return False

        paths = [self.repo_root / rel for rel in rel_paths]
        self._assert_paths_exist(paths)

        archive.parent.mkdir(parents=True, exist_ok=True)
        print(f"Caching {stage} artifacts for {source_hash}…")
        with tarfile.open(archive, "w:gz") as tar:
            for path, rel in zip(paths, rel_paths):
                tar.add(path, arcname=rel)

        rel_archive = archive.relative_to(self.worktree_path)
        self._run_git(["-C", str(self.worktree_path), "add", str(rel_archive)])
        diff = self._run_git(["-C", str(self.worktree_path), "diff", "--cached", "--quiet"], check=False)
        if diff.returncode == 0:
            return False

        message = f"Cache {stage} artifacts for {source_hash}"
        self._run_git(["-C", str(self.worktree_path), "commit", "-m", message])
        return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage build artifact cache branch.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("hash", help="Print the git tree hash for the sources directory.")

    restore_parser = sub.add_parser("restore", help="Restore cached artifacts.")
    restore_parser.add_argument("--stage", choices=["initial", "post"], required=True)
    restore_parser.add_argument("--hash", dest="source_hash", required=True)

    store_parser = sub.add_parser("store", help="Store artifacts in the cache branch.")
    store_parser.add_argument("--stage", choices=["initial", "post"], required=True)
    store_parser.add_argument("--hash", dest="source_hash", required=True)
    store_parser.add_argument("--paths", nargs="+", required=True, help="Relative paths to archive.")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    manager = CacheManager.create()

    if args.command == "hash":
        print(manager.compute_source_hash())
        return 0

    if args.command == "restore":
        restored = manager.restore(args.source_hash, args.stage)
        return 0 if restored else 1

    if args.command == "store":
        manager.store(args.source_hash, args.stage, args.paths)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
