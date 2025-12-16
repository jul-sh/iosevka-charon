#!/usr/bin/env python3
"""
Build custom Iosevka fonts from private build plans.

Steps:
  1. Install npm dependencies in the Iosevka subtree.
  2. Parse plan names from `private-build-plans.toml`.
  3. For each plan:
     - Build TTFs
     - Generate subsetted (Basic Latin) WOFF2 webfonts.
"""

import argparse
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import traceback
from typing import List, Optional

# Constants
# ----------------------------------------------------------------------------

# Directory structure
OUTPUT_DIR: str = "general_use_fonts"
WORKDIR: str = "sources/workdir"
REPO_DIR: str = "sources/iosevka"  # Git subtree containing Iosevka sources

# Build plan file (can be overridden via command-line argument)
PRIVATE_TOML: str = "sources/private-build-plans.toml"

# Utility Functions
# ----------------------------------------------------------------------------


def run_cmd(command: str, cwd: Optional[str] = None) -> None:
    """Executes a shell command and raises an error if it fails.

    Args:
        command: The shell command to execute.
        cwd: Optional working directory to run command in.

    Raises:
        subprocess.CalledProcessError: If command execution fails.
    """
    print(f"[cmd] {command}")
    try:
        subprocess.check_call(command, shell=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Command failed with exit code {e.returncode}")
        print(f"Command was: {command}")
        print(f"Working directory: {cwd or os.getcwd()}")
        raise


# Environment Setup
# ----------------------------------------------------------------------------


def prep_environment(build_plan_file: str) -> None:
    """Prepares the build environment.

    Copies build plans, installs dependencies, and cleans output directory.
    Note: Assumes the Iosevka subtree is already present.

    Args:
        build_plan_file: Path to the build plans TOML file.

    Raises:
        FileNotFoundError: If private build plans file is missing.
        Exception: If any preparation step fails.
    """
    try:
        os.makedirs(WORKDIR, exist_ok=True)

        # Copy private build plans
        print("[prep_environment] Copying build plans...")
        if not os.path.exists(build_plan_file):
            raise FileNotFoundError(f"Build plans file not found: {build_plan_file}")
        shutil.copyfile(
            build_plan_file, os.path.join(REPO_DIR, "private-build-plans.toml")
        )

        # Install npm dependencies
        print("[prep_environment] Installing npm dependencies...")
        run_cmd("npm ci", cwd=REPO_DIR)

        # Ensure output directory exists (Makefile handles cleaning)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    except Exception as e:
        print(f"ERROR during environment preparation: {str(e)}")
        print("Traceback:")
        traceback.print_exc()
        raise


# Build Plan Processing
# ----------------------------------------------------------------------------


def get_build_plans(build_plan_file: str) -> List[str]:
    """Parses build plan names from the specified build plans file.

    Args:
        build_plan_file: Path to the build plans TOML file.

    Returns:
        List of build plan names, excluding variant plans containing dots.

    Raises:
        FileNotFoundError: If build plans file is missing.
        Exception: If parsing fails.
    """
    try:
        plans: List[str] = []
        pattern = re.compile(r"^\[buildPlans\.(.+)\]$")
        with open(build_plan_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                match = pattern.match(line)
                if match:
                    plan_name = match.group(1)
                    if "." not in plan_name:
                        plans.append(plan_name)

        if not plans:
            print(f"WARNING: No build plans found in {build_plan_file}")

        return plans
    except FileNotFoundError:
        print(f"ERROR: Build plans file not found: {build_plan_file}")
        raise
    except Exception as e:
        print(f"ERROR parsing build plans: {str(e)}")
        raise


# Font Building
# ----------------------------------------------------------------------------


def build_one_plan(plan_name: str) -> None:
    """Builds a single font plan.

    Steps:
      1. npm run build -- ttf::<plan_name>
      2. Copy TTFs to OUTPUT_DIR/<plan_name>/ttf
      3. Generate WOFF2 webfonts to OUTPUT_DIR/<plan_name>/woff2

    Args:
        plan_name: Name of the build plan to process.
    """
    print(f"\n--- Building plan '{plan_name}' ---")

    plan_dist_dir = os.path.join(REPO_DIR, "dist", plan_name, "TTF")
    plan_out_dir = os.path.join(OUTPUT_DIR, plan_name)
    ttf_out_dir = os.path.join(plan_out_dir, "ttf")

    os.makedirs(ttf_out_dir, exist_ok=True)

    # 1) Build TTF
    print(f"[build_one_plan] Building TTF for '{plan_name}'...")
    run_cmd(f"npm run build -- ttf::{plan_name}", cwd=REPO_DIR)

    # 2) Copy TTFs
    if not os.path.isdir(plan_dist_dir):
        print(f"[build_one_plan] ERROR: Dist folder not found: {plan_dist_dir}")
        raise FileNotFoundError(f"Dist folder not found: {plan_dist_dir}")

    for filename in os.listdir(plan_dist_dir):
        if filename.endswith(".ttf"):
            shutil.copy2(os.path.join(plan_dist_dir, filename), ttf_out_dir)


def get_worker_count(plan_total: int) -> int:
    """Determine how many workers to use when building plans in parallel."""

    env_value = os.environ.get("IOSEVKA_BUILD_WORKERS")
    if env_value:
        try:
            value = int(env_value)
            if value > 0:
                return value
            print(
                "[get_worker_count] Ignoring non-positive IOSEVKA_BUILD_WORKERS value."
            )
        except ValueError:
            print(
                "[get_worker_count] Ignoring non-numeric IOSEVKA_BUILD_WORKERS value."
            )

    cpu_total = os.cpu_count() or 1
    return max(1, min(plan_total, cpu_total))


# Main Entry Point
# ----------------------------------------------------------------------------


def main() -> None:
    """Main entry point.

    Prepares environment, gathers build plans, and builds each plan in parallel.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Build custom Iosevka fonts from build plans."
    )
    parser.add_argument(
        "build_plan_file",
        nargs="?",
        default=PRIVATE_TOML,
        help=f"Path to the build plans TOML file (default: {PRIVATE_TOML})",
    )
    args = parser.parse_args()

    build_plan_file = args.build_plan_file
    if not build_plan_file:
        build_plan_file = PRIVATE_TOML

    print(f"[main] Working directory: {os.getcwd()}")
    print(f"[main] Build plan file: {build_plan_file}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(WORKDIR, exist_ok=True)
    try:
        prep_environment(build_plan_file)

        build_plans = get_build_plans(build_plan_file)
        print("[main] Discovered build plans:", build_plans)

        if not build_plans:
            print("No build plans to process.")
            return

        worker_count = get_worker_count(len(build_plans))
        print(f"[main] Building with up to {worker_count} parallel worker(s).")

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=worker_count
        ) as executor:
            future_to_plan = {
                executor.submit(build_one_plan, name): name for name in build_plans
            }

            for future in concurrent.futures.as_completed(future_to_plan):
                plan_name = future_to_plan[future]
                try:
                    future.result()
                    print(f"[main] Plan '{plan_name}' completed.")
                except Exception as e:
                    print(f"ERROR building plan '{plan_name}': {str(e)}")
                    print("Traceback:")
                    traceback.print_exc()
                    raise

        print("\nAll font builds completed successfully.")
    except Exception as e:
        print(f"\nERROR: Font build failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
