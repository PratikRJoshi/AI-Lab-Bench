#!/usr/bin/env bash
# Refresh AWS credentials and restart the server.
#
# Usage — two equivalent ways:
#
#   1. Export first, then run (simplest):
#        export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_SESSION_TOKEN=...
#        ./refresh.sh
#
#   2. Pass as arguments directly:
#        ./refresh.sh "$AWS_ACCESS_KEY_ID" "$AWS_SECRET_ACCESS_KEY" "$AWS_SESSION_TOKEN"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
cd "$SCRIPT_DIR"

# ── Parse credentials ─────────────────────────────────────────────────────────

if [ $# -eq 3 ]; then
  KEY_ID="$1"
  SECRET="$2"
  SESSION="$3"
elif [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ] && [ -n "$AWS_SESSION_TOKEN" ]; then
  KEY_ID="$AWS_ACCESS_KEY_ID"
  SECRET="$AWS_SECRET_ACCESS_KEY"
  SESSION="$AWS_SESSION_TOKEN"
  echo "Using credentials from current shell environment."
else
  echo "No credentials found. Export them first:"
  echo "  export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_SESSION_TOKEN=..."
  echo "  ./refresh.sh"
  exit 1
fi

# ── Validate ──────────────────────────────────────────────────────────────────

if [ -z "$KEY_ID" ] || [ -z "$SECRET" ] || [ -z "$SESSION" ]; then
  echo "Error: one or more credentials are empty. Aborting."
  exit 1
fi

# ── Write to .env ─────────────────────────────────────────────────────────────

update_or_append() {
  local key="$1" val="$2"
  # Use grep/sed pattern that handles = inside values (session tokens contain =)
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    grep -v "^${key}=" "$ENV_FILE" > "$ENV_FILE.tmp"
    echo "${key}=${val}" >> "$ENV_FILE.tmp"
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
