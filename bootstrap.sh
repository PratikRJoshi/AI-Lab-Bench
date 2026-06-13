#!/usr/bin/env bash
# One-shot bootstrap for the url-truth-analyzer Firefox extension on a fresh
# macOS machine. After this completes, the only thing left is to load the
# extension in Firefox via about:debugging.
#
#   curl … | bash    # works
#   ./bootstrap.sh   # also works
#
# Idempotent: re-running skips work that's already done.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$REPO_ROOT/LLM_Skills/url-truth-analyzer"
SKILL_LINK="$HOME/.claude/skills/url-truth-analyzer"
EXTENSION_DIR="$REPO_ROOT/LLM_Skills/truth-analyzer-extension"

green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
red()    { printf "\033[31m%s\033[0m\n" "$*"; }

# ── 0. Platform check ──────────────────────────────────────────────────
if [[ "$(uname -s)" != "Darwin" ]]; then
  red "This bootstrap is macOS-only (uses Homebrew)."
  echo "    On Linux: install yt-dlp, ffmpeg, tesseract, pandoc via your package manager,"
  echo "    then run $EXTENSION_DIR/install.sh."
  exit 1
fi

# ── 1. Homebrew ────────────────────────────────────────────────────────
if ! command -v brew >/dev/null 2>&1; then
  green "▶ Installing Homebrew (you may be prompted for your password)…"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Apple Silicon brew lives at /opt/homebrew; Intel at /usr/local. Add to PATH for this session.
  if [[ -x /opt/homebrew/bin/brew ]]; then eval "$(/opt/homebrew/bin/brew shellenv)"; fi
  if [[ -x /usr/local/bin/brew ]]; then eval "$(/usr/local/bin/brew shellenv)"; fi
fi

# ── 2. Skill runtime tools (system) ────────────────────────────────────
green "▶ Installing system tools via Homebrew (skips already-installed)…"
brew_install() {
  if brew list --formula "$1" >/dev/null 2>&1; then
    echo "  ✓ $1 already installed"
  else
    brew install "$1"
  fi
}
brew_install python
brew_install yt-dlp
brew_install ffmpeg
brew_install tesseract
brew_install pandoc
# node is needed only for `web-ext`, the Mozilla CLI that auto-loads the
# Firefox extension when start.sh runs.
brew_install node

# ── 2b. web-ext (auto-launch the extension when start.sh runs) ─────────
if ! command -v web-ext >/dev/null 2>&1; then
  green "▶ Installing web-ext (auto-loads the extension into Firefox)…"
  npm install --global web-ext
else
  echo "  ✓ web-ext already installed"
fi

# ── 3. Python tools the skill needs ────────────────────────────────────
green "▶ Installing Python packages used by the skill…"
# These have to be on PATH for the skill (which spawns subprocesses), so we
# install them user-global, not in the extension's venv.
PIP="$(command -v pip3 || command -v pip)"
"$PIP" install --user --upgrade --quiet \
  openai-whisper \
  trafilatura \
  playwright

# ── 4. Playwright Chromium browser ─────────────────────────────────────
# Required for Instagram carousel scraping (Mode F). One-time download.
if ! python3 -c "from playwright.sync_api import sync_playwright; \
     sync_playwright().__enter__().chromium.launch(headless=True).close()" \
     >/dev/null 2>&1; then
  green "▶ Downloading Playwright Chromium (one-time, ~150 MB)…"
  python3 -m playwright install chromium
else
  echo "  ✓ Playwright Chromium already available"
fi

# ── 5. Claude CLI ──────────────────────────────────────────────────────
if ! command -v claude >/dev/null 2>&1; then
  red "claude CLI not found on PATH."
  echo "    Install Claude Code: https://claude.com/code"
  echo "    Re-run this script once it's installed."
  exit 1
fi

green "▶ Verifying Claude CLI auth…"
if ! claude --print "ping" >/dev/null 2>&1; then
  red "claude --print failed. Run 'claude' interactively once to log in, then re-run this script."
  exit 1
fi

# ── 6. Register the skill globally ─────────────────────────────────────
green "▶ Registering url-truth-analyzer skill in ~/.claude/skills/…"
mkdir -p "$(dirname "$SKILL_LINK")"
if [[ -L "$SKILL_LINK" ]]; then
  current="$(readlink "$SKILL_LINK")"
  if [[ "$current" != "$SKILL_SRC" ]]; then
    yellow "  Existing symlink points to $current — replacing with $SKILL_SRC"
    ln -sfn "$SKILL_SRC" "$SKILL_LINK"
  else
    echo "  ✓ symlink already correct"
  fi
elif [[ -e "$SKILL_LINK" ]]; then
  red "  $SKILL_LINK exists and isn't a symlink. Move it aside, then re-run."
  exit 1
else
  ln -s "$SKILL_SRC" "$SKILL_LINK"
fi

# ── 7. Run the extension installer ─────────────────────────────────────
green "▶ Setting up the backend + Python venv…"
"$EXTENSION_DIR/install.sh"

# ── 8. Done ────────────────────────────────────────────────────────────
cat <<EOF

$(green "✓ Bootstrap complete.")
Backend running on http://localhost:5757 (logs: /tmp/truth-analyzer.log)

One thing left — load the Firefox extension (one-time per Firefox profile):
  1. Open Firefox → about:debugging
  2. "This Firefox" → "Load Temporary Add-on…"
  3. Pick: $EXTENSION_DIR/extension/manifest.json

Then click the 🔍 toolbar icon on any page (or right-click → Analyze with
Truth Analyzer). Channel/profile home pages auto-expand to top-10 batches.
EOF
