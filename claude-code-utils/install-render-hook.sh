#!/usr/bin/env bash
# Symlinks render-skill-output.py into ~/.claude/hooks and registers it as a Stop hook (idempotent).
set -euo pipefail

command -v jq >/dev/null || { echo "jq is required: brew install jq"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SETTINGS="$HOME/.claude/settings.json"
HOOK_CMD='python3 "$HOME/.claude/hooks/render-skill-output.py" 2>/dev/null || true'

mkdir -p "$HOME/.claude/hooks"
ln -sf "$SCRIPT_DIR/hooks/render-skill-output.py" "$HOME/.claude/hooks/render-skill-output.py"

[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
if jq -e --arg c "$HOOK_CMD" '[.hooks.Stop[]?.hooks[]?.command] | index($c)' "$SETTINGS" >/dev/null; then
  echo "Stop hook already registered"
else
  jq --arg c "$HOOK_CMD" '.hooks.Stop += [{"matcher":"","hooks":[{"type":"command","command":$c,"timeout":20}]}]' \
    "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"
  echo "Stop hook registered in $SETTINGS"
fi
