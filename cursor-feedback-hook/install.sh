#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OBS_DIR="$HOME/.concise-observer"
CURSOR_HOOKS="$HOME/.cursor/hooks.json"
HOOK_ENTRY='{"command":"'"$OBS_DIR"'/rate-dialog.sh","timeout":30}'

# --- Prerequisites -----------------------------------------------------------
missing=()
for cmd in jq python3 sqlite3 osascript; do
  command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "WARNING: missing prerequisites: ${missing[*]}"
  echo "  jq:        brew install jq"
  echo "  python3:   comes with macOS / brew install python3"
  echo "  sqlite3:   comes with macOS"
  echo "  osascript: macOS only (this hook requires macOS)"
  echo ""
  echo "Install missing tools and re-run, or continue at your own risk."
  read -rp "Continue anyway? [y/N] " ans
  [[ "$ans" =~ ^[Yy] ]] || exit 1
fi

# --- Install rate-dialog.sh --------------------------------------------------
mkdir -p "$OBS_DIR"
cp "$SCRIPT_DIR/rate-dialog.sh" "$OBS_DIR/rate-dialog.sh"
chmod +x "$OBS_DIR/rate-dialog.sh"
echo "Installed rate-dialog.sh -> $OBS_DIR/rate-dialog.sh"

# --- Merge into Cursor hooks.json --------------------------------------------
if [ -d "$HOME/.cursor" ]; then
  if [ ! -f "$CURSOR_HOOKS" ]; then
    cat > "$CURSOR_HOOKS" << 'HOOKJSON'
{
  "version": 1,
  "hooks": {
    "stop": []
  }
}
HOOKJSON
    echo "Created $CURSOR_HOOKS"
  fi

  already="$(jq -r '.hooks.stop // [] | map(.command) | join("\n")' "$CURSOR_HOOKS" 2>/dev/null)"
  if echo "$already" | grep -qF "rate-dialog.sh"; then
    echo "Cursor stop hook already wired — skipping."
  else
    tmp="$(mktemp)"
    jq --argjson entry "$HOOK_ENTRY" \
      '.hooks.stop = ((.hooks.stop // []) + [$entry])' \
      "$CURSOR_HOOKS" > "$tmp" && mv "$tmp" "$CURSOR_HOOKS"
    echo "Added stop hook to $CURSOR_HOOKS"
  fi
else
  echo "Cursor not found at ~/.cursor — skipping Cursor hook wiring."
fi

# --- Optionally wire for Claude Code -----------------------------------------
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
if [ -d "$HOME/.claude" ]; then
  echo ""
  read -rp "Wire for Claude Code too? [y/N] " ans
  if [[ "$ans" =~ ^[Yy] ]]; then
    if [ ! -f "$CLAUDE_SETTINGS" ]; then
      echo '{"hooks":{"Stop":[]}}' | jq '.' > "$CLAUDE_SETTINGS"
      echo "Created $CLAUDE_SETTINGS"
    fi

    already="$(jq -r '.hooks.Stop // [] | map(.command) | join("\n")' "$CLAUDE_SETTINGS" 2>/dev/null)"
    if echo "$already" | grep -qF "rate-dialog.sh"; then
      echo "Claude Code Stop hook already wired — skipping."
    else
      tmp="$(mktemp)"
      jq --argjson entry "$HOOK_ENTRY" \
        '.hooks.Stop = ((.hooks.Stop // []) + [$entry])' \
        "$CLAUDE_SETTINGS" > "$tmp" && mv "$tmp" "$CLAUDE_SETTINGS"
      echo "Added Stop hook to $CLAUDE_SETTINGS"
    fi
  fi
fi

echo ""
echo "Done. The feedback dialog will pop up after each agent response."
echo "Feedback is logged to $OBS_DIR/feedback.jsonl"
