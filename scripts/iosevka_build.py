#!/usr/bin/env python3
"""
Build custom Iosevka fonts from private build plans.

Steps:
  1. Install npm dependencies in the Iosevka subtree.
  2. Parse plan names from `private-build-plans.toml`.
  3. For each plan:
     - Build TTFs
"""

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import trio

# Constants
# ----------------------------------------------------------------------------

# Directory structure
OUTPUT_DIR = Path("unprocessed_fonts")
WORK_DIR = Path("sources/workdir")
REPO_DIR = Path("sources/iosevka")  # Git subtree containing Iosevka sources

# Build plan file (can be overridden via command-line argument)
PRIVATE_TOML = Path("sources/private-build-plans.toml")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Utility Functions
# ----------------------------------------------------------------------------


async def run_cmd(command: str, cwd: Optional[Path] = None) -> None:
    """Executes a shell command asynchronously and raises an error if it fails.

    Args:
        command: The shell command to execute.
        cwd: Optional working directory to run command in.

    Raises:
        subprocess.CalledProcessError: If command execution fails.
    """
    logger.info(f"Running command: {command}")
    try:
        # Use trio.run_process for async subprocess execution
        result = await trio.run_process(
            command,
            shell=True,
            cwd=cwd,
            check=False,  # We'll handle the error ourselves
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, command)
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}")
        logger.error(f"Command: {command}")
        logger.error(f"CWD: {cwd or Path.cwd()}")
        raise


# Environment Setup
# ----------------------------------------------------------------------------


async def prep_environment(build_plan_file: Path) -> None:
    """Prepares the build environment.

    Copies build plans, installs dependencies, and cleans output directory.
    Note: Assumes the Iosevka subtree is already present.

    Args:
        build_plan_file: Path to the build plans TOML file.

    Raises:
        FileNotFoundError: If private build plans file is missing.
    """
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    # Copy private build plans
    logger.info("Copying build plans...")
    if not build_plan_file.exists():
        raise FileNotFoundError(f"Build plans file not found: {build_plan_file}")

    target_toml = REPO_DIR / "private-build-plans.toml"
    shutil.copyfile(build_plan_file, target_toml)

    # Install npm dependencies
    logger.info("Installing npm dependencies...")
    await run_cmd("npm ci", cwd=REPO_DIR)

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Build Plan Processing
# ----------------------------------------------------------------------------


def get_build_plans(build_plan_file: Path) -> List[str]:
    """Parses build plan names from the specified build plans file.

    Args:
        build_plan_file: Path to the build plans TOML file.

    Returns:
        List of build plan names, excluding variant plans containing dots.
    """
    plans: List[str] = []
    # Match lines like [buildPlans.iosevkacharon] but not [buildPlans.iosevkacharon.something]
    pattern = re.compile(r"^\[buildPlans\.([^.]+)\]$")

    try:
        with open(build_plan_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                match = pattern.match(line)
                if match:
                    plans.append(match.group(1))

        if not plans:
            logger.warning(f"No build plans found in {build_plan_file}")

        return plans
    except Exception as e:
        logger.error(f"Error parsing build plans: {e}")
        raise


# Font Building
# ----------------------------------------------------------------------------


async def build_one_plan(plan_name: str) -> None:
    """Builds a single font plan.

    Steps:
      1. npm run build -- ttf::<plan_name>
      2. Copy TTFs to OUTPUT_DIR/<plan_name>/ttf

    Args:
        plan_name: Name of the build plan to process.
    """
    logger.info(f"--- Building plan '{plan_name}' ---")

    plan_dist_dir = REPO_DIR / "dist" / plan_name / "TTF"
    ttf_out_dir = OUTPUT_DIR / plan_name / "ttf"

    ttf_out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Build TTF
    logger.info(f"Building TTF for '{plan_name}'...")
    await run_cmd(f"npm run build -- ttf::{plan_name}", cwd=REPO_DIR)

    # 2) Copy TTFs
    if not plan_dist_dir.is_dir():
        logger.error(f"Dist folder not found: {plan_dist_dir}")
        raise FileNotFoundError(f"Dist folder not found: {plan_dist_dir}")

    for file in plan_dist_dir.glob("*.ttf"):
        shutil.copy2(file, ttf_out_dir)


def get_worker_count(plan_total: int) -> int:
    """Determine how many workers to use when building plans in parallel."""
    env_value = os.environ.get("IOSEVKA_BUILD_WORKERS")
    if env_value:
        try:
            value = int(env_value)
            if value > 0:
                return value
            logger.warning("Ignoring non-positive IOSEVKA_BUILD_WORKERS value.")
        except ValueError:
            logger.warning("Ignoring non-numeric IOSEVKA_BUILD_WORKERS value.")

    cpu_total = os.cpu_count() or 1
    return max(1, min(plan_total, cpu_total))


# Main Entry Point
# ----------------------------------------------------------------------------


async def async_main() -> None:
    """Async main entry point."""
    parser = argparse.ArgumentParser(
        description="Build custom Iosevka fonts from build plans."
    )
    parser.add_argument(
        "build_plan_file",
        nargs="?",
        type=Path,
        default=PRIVATE_TOML,
        help=f"Path to the build plans TOML file (default: {PRIVATE_TOML})",
    )
    args = parser.parse_args()

    build_plan_file: Path = args.build_plan_file

    logger.info(f"Working directory: {Path.cwd()}")
    logger.info(f"Build plan file: {build_plan_file}")

    try:
        await prep_environment(build_plan_file)

        build_plans = get_build_plans(build_plan_file)
        if not build_plans:
            logger.info("No build plans to process.")
            return

        logger.info(f"Discovered build plans: {', '.join(build_plans)}")

        worker_count = get_worker_count(len(build_plans))
        logger.info(f"Building with up to {worker_count} parallel worker(s).")

        # Track errors for reporting
        errors: List[tuple] = []

        async def build_plan_async(
            plan_name: str,
            limiter: trio.CapacityLimiter,
        ) -> None:
            """Async wrapper for building a single plan."""
            async with limiter:
                try:
                    await build_one_plan(plan_name)
                    logger.info(f"Plan '{plan_name}' completed.")
                except Exception as e:
                    logger.error(f"Error building plan '{plan_name}': {e}")
                    errors.append((plan_name, e))

        limiter = trio.CapacityLimiter(worker_count)
        async with trio.open_nursery() as nursery:
            for plan_name in build_plans:
                nursery.start_soon(build_plan_async, plan_name, limiter)

        if errors:
            raise RuntimeError(f"Failed to build {len(errors)} plan(s)")

        logger.info("All font builds completed successfully.")
    except Exception as e:
        logger.critical(f"Font build failed: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            import traceback
            traceback.print_exc()
        sys.exit(1)


def main() -> None:
    """Entry point - runs the async main function."""
    trio.run(async_main)


if __name__ == "__main__":
    main()
