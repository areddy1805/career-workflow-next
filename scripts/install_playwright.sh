#!/usr/bin/env bash
# PH5: pin Playwright browser binaries into the project (do NOT rely on a
# global install — user recommendation 2026-08-02).
#
# - playwright version is pinned in requirements.txt (playwright==1.61.0);
#   each playwright version downloads its exact browser build via `playwright
#   install`, so pinning the package pins the binaries.
# - Browsers land in <repo>/.playwright (project-local, gitignored) so every
#   machine/CI uses the identical revision.
#
# Usage: scripts/install_playwright.sh
set -euo pipefail
cd "$(dirname "$0")/.."

export PLAYWRIGHT_BROWSERS_PATH="$(pwd)/.playwright"
export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0

if ! .venv/bin/python -c "import playwright" 2>/dev/null; then
  echo "installing pinned playwright package..."
  .venv/bin/pip install -r requirements.txt >/dev/null
fi

echo "installing chromium (pinned to playwright==$(.venv/bin/playwright --version)) into .playwright/ ..."
.venv/bin/playwright install chromium

echo "OK — browsers pinned at $PLAYWRIGHT_BROWSERS_PATH"
echo "Set PLAYWRIGHT_BROWSERS_PATH=$(pwd)/.playwright when running PH5 code/tests."
