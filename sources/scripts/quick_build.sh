#!/usr/bin/env bash
#
# Quick build script for fast iteration - builds only IosevkaCharon Regular
# Usage: bash sources/scripts/quick_build.sh

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Source the Nix environment
source sources/scripts/setup_shell.sh

echo "Quick build: IosevkaCharon Regular only..."

# Run the build for just Regular weight
python3 -c "
import os
import subprocess
import shutil
import sys
from pathlib import Path

sys.path.append('sources/scripts')
import fix_fonts

REPO_DIR = 'sources/iosevka'
OUTPUT_DIR = 'sources/output/quick'
PRIVATE_TOML = 'sources/private-build-plans.toml'

# Prepare environment
os.makedirs(OUTPUT_DIR, exist_ok=True)
shutil.copyfile(PRIVATE_TOML, os.path.join(REPO_DIR, 'private-build-plans.toml'))

# Install npm dependencies if needed
if not os.path.exists(os.path.join(REPO_DIR, 'node_modules')):
    print('[quick_build] Installing npm dependencies...')
    subprocess.check_call('npm ci', shell=True, cwd=REPO_DIR)

# Build just Regular
print('[quick_build] Building IosevkaCharon Regular...')
subprocess.check_call('npm run build -- ttf::IosevkaCharon', shell=True, cwd=REPO_DIR)

# Copy only Regular.ttf
plan_dist_dir = os.path.join(REPO_DIR, 'dist', 'IosevkaCharon', 'TTF')
regular_paths = []
for filename in os.listdir(plan_dist_dir):
    if 'Regular.ttf' in filename:
        dst = os.path.join(OUTPUT_DIR, filename)
        shutil.copy2(os.path.join(plan_dist_dir, filename), dst)
        regular_paths.append(dst)
        print(f'[quick_build] Copied {filename} to {OUTPUT_DIR}')

for font_path in regular_paths:
    print(f'[quick_build] Post-processing {font_path}...')
    fix_fonts.post_process_font(Path(font_path))

print('[quick_build] Done! Regular font at sources/output/quick/')
"
