#!/usr/bin/env python3
"""
Build custom Iosevka fonts from private build plans.

Steps:
  1. Clone or update the Iosevka repo at a specific commit.
  2. Install npm dependencies.
  3. Parse plan names from `private-build-plans.toml`.
  4. For each plan:
     - Build TTFs
     - Generate subsetted (Basic Latin) WOFF2 webfonts.
"""

import os
import re
import shutil
import subprocess
import sys
import traceback
from typing import List, Optional

# Constants
# ----------------------------------------------------------------------------

# Repository information
IOSEVKA_REPO_URL: str = "https://github.com/be5invis/Iosevka.git"
IOSEVKA_VERSION: str = "v33.2.0"

# Directory structure
OUTPUT_DIR: str = "sources/output"
WORKDIR: str = "sources/workdir"
REPO_DIR: str = os.path.join(WORKDIR, "iosevka-repo")
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

def prep_environment() -> None:
    """Prepares the build environment.

    Ensures WORKDIR exists, clones/updates Iosevka repo, checks out specified commit,
    copies build plans, installs dependencies, and cleans output directory.

    Raises:
        FileNotFoundError: If private build plans file is missing.
        Exception: If any preparation step fails.
    """
    try:
        os.makedirs(WORKDIR, exist_ok=True)

        # Clone or update the repository
        if os.path.isdir(REPO_DIR):
            print("[prep_environment] Updating existing Iosevka repository...")
            run_cmd("git fetch --all --tags", cwd=REPO_DIR)
            run_cmd(f"git checkout {IOSEVKA_VERSION}", cwd=REPO_DIR)
            run_cmd("git pull", cwd=REPO_DIR)
            run_cmd("git clean -fdx", cwd=REPO_DIR)
        else:
            print("[prep_environment] Cloning Iosevka repository...")
            run_cmd(
                f"git clone --branch {IOSEVKA_VERSION} {IOSEVKA_REPO_URL} {REPO_DIR}"
            )

        # Copy private build plans
        print("[prep_environment] Copying private build plans...")
        if not os.path.exists(PRIVATE_TOML):
            raise FileNotFoundError(f"Private build plans file not found: {PRIVATE_TOML}")
        shutil.copyfile(PRIVATE_TOML, os.path.join(REPO_DIR, "private-build-plans.toml"))

        # Install npm dependencies
        print("[prep_environment] Installing npm dependencies...")
        run_cmd("npm ci", cwd=REPO_DIR)

        # Clean the output directory
        if os.path.isdir(OUTPUT_DIR):
            print(f"[prep_environment] Cleaning output directory: '{OUTPUT_DIR}'...")
            for item in os.listdir(OUTPUT_DIR):
                item_path = os.path.join(OUTPUT_DIR, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                else:
                    shutil.rmtree(item_path)
        else:
            os.makedirs(OUTPUT_DIR, exist_ok=True)

    except Exception as e:
        print(f"ERROR during environment preparation: {str(e)}")
        print("Traceback:")
        traceback.print_exc()
        raise

# Build Plan Processing
# ----------------------------------------------------------------------------

def get_build_plans() -> List[str]:
    """Parses build plan names from private-build-plans.toml.

    Returns:
        List of build plan names, excluding variant plans containing dots.

    Raises:
        FileNotFoundError: If build plans file is missing.
        Exception: If parsing fails.
    """
    try:
        plans: List[str] = []
        pattern = re.compile(r'^\[buildPlans\.(.+)\]$')
        with open(PRIVATE_TOML, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                match = pattern.match(line)
                if match:
                    plan_name = match.group(1)
                    if '.' not in plan_name:
                        plans.append(plan_name)

        if not plans:
            print("WARNING: No build plans found in private-build-plans.toml")

        return plans
    except FileNotFoundError:
        print(f"ERROR: Build plans file not found: {PRIVATE_TOML}")
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


# Main Entry Point
# ----------------------------------------------------------------------------

def main() -> None:
    """Main entry point.

    Prepares environment, gathers build plans, and builds each plan in turn.
    """
    print(f"[main] Working directory: {os.getcwd()}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(WORKDIR, exist_ok=True)
    try:
        prep_environment()

        build_plans = get_build_plans()
        print("[main] Discovered build plans:", build_plans)

        for plan_name in build_plans:
            try:
                build_one_plan(plan_name)
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
