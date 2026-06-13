#!/usr/bin/env bash
# One-shot installer for the Truth Analyzer extension on a fresh machine.
# Run from anywhere — it cd's into its own directory.
#
# Usage: ./install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"

green() { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
red() { printf "\033[31m%s\033[0m\n" "$*"; }

# ── 1. Required binaries ───────────────────────────────────────────────
require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    red "Missing required tool: $1"
    echo "    Install hint: $2"
    exit 1
  fi
}

green "▶ Checking required tools…"
require python3 "brew install python (or use your distro's package manager)"
require claude  "Install Claude Code from https://claude.com/code"
require yt-dlp  "brew install yt-dlp"
require tesseract "brew install tesseract"

# whisper is a Python tool; the skill calls it via the system PATH.
if ! command -v whisper >/dev/null 2>&1; then
  yellow "⚠  'whisper' not on PATH. Install with: pip install -U openai-whisper"
  yellow "   (Required only for video/audio analysis. Skip if you only do articles.)"
fi

# ── 2. Verify claude CLI is logged in ──────────────────────────────────
green "▶ Verifying Claude CLI auth…"
if ! claude --print "ping" >/dev/null 2>&1; then
  red "claude --print failed. Run 'claude' interactively once to log in, then re-run this script."
  exit 1
fi

# ── 3. Backend venv + Python deps ──────────────────────────────────────
green "▶ Setting up backend Python virtualenv…"
cd "$BACKEND_DIR"
if [ ! -d truth-analyzer-env ]; then
  python3 -m venv truth-analyzer-env
fi
truth-analyzer-env/bin/pip install --quiet --upgrade pip
truth-analyzer-env/bin/pip install --quiet -r requirements.txt

# ── 4. .env ────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  green "▶ Creating .env from .env.example…"
  cp .env.example .env
fi

# ── 5. Smoke test the backend boots ────────────────────────────────────
green "▶ Smoke-testing the backend…"
./start.sh >/dev/null

# ── 6. Done ────────────────────────────────────────────────────────────
cat <<EOF

$(green "✓ Install complete.")
Backend running on http://localhost:5757 (logs: /tmp/truth-analyzer.log)

Next: load the Firefox extension (one-time, per Firefox profile):
  1. Open Firefox → about:debugging
  2. "This Firefox" → "Load Temporary Add-on…"
  3. Pick: $SCRIPT_DIR/extension/manifest.json

Then click the 🔍 toolbar icon on any page to analyze it.

Manage the backend later with:
  ./backend/start.sh   — start (kills any existing instance first)
  kill \$(cat /tmp/truth-analyzer.pid)   — stop
EOF
