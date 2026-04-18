#!/usr/bin/env bash
# Refresh AWS credentials and restart the server automatically.
# Usage:
#   Interactive (prompts for each value):
#       ./refresh.sh
#
#   Paste all three at once (export ... format from AWS console):
#       ./refresh.sh --paste
#
#   Pass directly as arguments:
#       ./refresh.sh ACCESS_KEY_ID SECRET_KEY SESSION_TOKEN

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
cd "$SCRIPT_DIR"

# ── Parse credentials ─────────────────────────────────────────────────────────

if [ "$1" = "--paste" ]; then
  echo "Paste the three 'export' lines from your AWS console, then press Enter twice:"
  echo ""
  PASTE_BLOCK=""
  while IFS= read -r line; do
    [ -z "$line" ] && break
    PASTE_BLOCK="$PASTE_BLOCK $line"
  done

  KEY_ID=$(echo "$PASTE_BLOCK"    | grep -o 'AWS_ACCESS_KEY_ID=[^ ]*'    | cut -d= -f2)
  SECRET=$(echo "$PASTE_BLOCK"    | grep -o 'AWS_SECRET_ACCESS_KEY=[^ ]*' | cut -d= -f2)
  SESSION=$(echo "$PASTE_BLOCK"   | grep -o 'AWS_SESSION_TOKEN=[^ ]*'     | cut -d= -f2)

elif [ $# -eq 3 ]; then
  KEY_ID="$1"
  SECRET="$2"
  SESSION="$3"

else
  echo "Enter your AWS credentials (values only, not the export lines):"
  read -rp "AWS_ACCESS_KEY_ID:     " KEY_ID
  read -rsp "AWS_SECRET_ACCESS_KEY: " SECRET; echo ""
  read -rp "AWS_SESSION_TOKEN:     " SESSION
fi

# ── Validate ──────────────────────────────────────────────────────────────────

if [ -z "$KEY_ID" ] || [ -z "$SECRET" ] || [ -z "$SESSION" ]; then
  echo "Error: one or more credentials are empty. Aborting."
  exit 1
fi

# ── Write to .env (update existing or append) ─────────────────────────────────

update_or_append() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    # Use awk to safely replace value (handles special chars in session token)
    awk -v k="$key" -v v="$val" 'BEGIN{FS=OFS="="} $1==k{$2=v} 1' "$ENV_FILE" > "$ENV_FILE.tmp"
    mv "$ENV_FILE.tmp" "$ENV_FILE"
  else
    echo "${key}=${val}" >> "$ENV_FILE"
  fi
}

update_or_append "AWS_ACCESS_KEY_ID"     "$KEY_ID"
update_or_append "AWS_SECRET_ACCESS_KEY" "$SECRET"
update_or_append "AWS_SESSION_TOKEN"     "$SESSION"

echo "Credentials written to .env"

# ── Restart server ────────────────────────────────────────────────────────────

echo "Restarting server..."
"$SCRIPT_DIR/start.sh"
