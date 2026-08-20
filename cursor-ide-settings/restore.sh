#!/usr/bin/env bash
set -euo pipefail

# Restore Cursor user settings, keybindings, and extensions on a new Mac.
# Usage: ./restore.sh

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${HOME}/Library/Application Support/Cursor/User"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This restore script currently supports macOS only." >&2
  exit 1
fi

mkdir -p "$DEST"
STAMP=$(date +%Y%m%d-%H%M%S)

backup_if_exists() {
  local file="$1"
  if [[ -f "$DEST/$file" ]]; then
    cp "$DEST/$file" "$DEST/${file}.bak.${STAMP}"
    echo "Backed up existing $file -> ${file}.bak.${STAMP}"
  fi
}

backup_if_exists settings.json
backup_if_exists keybindings.json

cp "$SRC/User/settings.json" "$DEST/settings.json"
cp "$SRC/User/keybindings.json" "$DEST/keybindings.json"
echo "Copied settings.json and keybindings.json"

MCP_DEST="${HOME}/.cursor/mcp.json"
mkdir -p "${HOME}/.cursor"
if [[ -f "$MCP_DEST" ]]; then
  cp "$MCP_DEST" "${MCP_DEST}.bak.${STAMP}"
  cp "$SRC/mcp.json" "${HOME}/.cursor/mcp.json.example"
  echo "Left existing ~/.cursor/mcp.json in place. Template saved as mcp.json.example"
else
  cp "$SRC/mcp.json" "$MCP_DEST"
  echo "Copied mcp.json (fill every REPLACE_ME before use)"
fi

if ! command -v cursor >/dev/null 2>&1; then
  echo "cursor CLI not found. Install Cursor, then run: cursor --list-extensions" >&2
  echo "To install extensions later: xargs -n1 cursor --install-extension < \"$SRC/extensions.txt\""
  exit 0
fi

echo "Installing extensions..."
while IFS= read -r ext; do
  [[ -z "$ext" || "$ext" =~ ^# ]] && continue
  cursor --install-extension "$ext" || echo "Skipped: $ext"
done < "$SRC/extensions.txt"

echo "Done. Reload Cursor (Cmd+Shift+P → Developer: Reload Window)."
echo "Update machine-specific paths in settings.json if this Mac uses different Java or cert paths."
