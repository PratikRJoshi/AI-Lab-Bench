#!/usr/bin/env bash
# Start the Truth Analyzer backend, then launch a dedicated Firefox window
# with the extension auto-loaded via Mozilla's `web-ext` CLI.
#
# The Firefox window uses a persistent profile dir (so IG cookies, bookmarks,
# etc. survive across runs). Set SKIP_FIREFOX_AUTOLAUNCH=1 to start only the
# backend (useful when you load the extension manually in your main Firefox).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTENSION_DIR="$(cd "$SCRIPT_DIR/../extension" && pwd)"
PROFILE_DIR="${TRUTH_ANALYZER_FIREFOX_PROFILE:-$HOME/.config/truth-analyzer/firefox-profile}"
WEBEXT_PIDFILE="/tmp/truth-analyzer-webext.pid"
cd "$SCRIPT_DIR"

if [ ! -d "truth-analyzer-env" ]; then
  echo "Virtual environment not found. Run ../install.sh (or ./setup.sh) first."
  exit 1
fi

# ── Backend ────────────────────────────────────────────────────────────
# Refuse to kill a backend that has analyses in flight unless the user opts
# in (FORCE=1 or interactive y). Each in-flight job's claude --print
# subprocess and SSE stream die with the parent process — so a careless
# restart loses your running analyses and any completed ones still in memory.
if running_count="$(curl -s --max-time 2 http://localhost:5757/health \
                    | python3 -c 'import sys,json;print(json.load(sys.stdin).get("running",0))' \
                    2>/dev/null)" && [ -n "$running_count" ] && [ "$running_count" -gt 0 ]; then
  if [ "${FORCE:-0}" = "1" ]; then
    echo "⚠  $running_count analysis/analyses in flight — killing anyway (FORCE=1)."
  elif [ -t 0 ]; then
    printf "⚠  %s analysis/analyses in flight. Kill anyway? [y/N] " "$running_count"
    read -r answer
    case "$answer" in
      y|Y|yes|YES) ;;
      *) echo "Aborted. Re-run with FORCE=1 to skip this prompt."; exit 1 ;;
    esac
  else
    echo "⚠  $running_count analysis/analyses in flight and stdin is not a TTY."
    echo "   Aborting to avoid data loss. Re-run with FORCE=1 to override."
    exit 1
  fi
fi

lsof -ti :5757 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

echo "Starting Truth Analyzer backend on http://localhost:5757"
echo "Logs: tail -f /tmp/truth-analyzer.log"
nohup truth-analyzer-env/bin/python server.py > /tmp/truth-analyzer.log 2>&1 &
echo $! > /tmp/truth-analyzer.pid

sleep 2
if curl -s http://localhost:5757/health | grep -q '"ok"'; then
  echo "Server is up (PID $(cat /tmp/truth-analyzer.pid))"
else
  echo "Server failed to start. Check: tail -20 /tmp/truth-analyzer.log"
  exit 1
fi

# ── Firefox auto-launch (web-ext) ──────────────────────────────────────
if [ "${SKIP_FIREFOX_AUTOLAUNCH:-0}" = "1" ]; then
  echo "Firefox auto-launch skipped (SKIP_FIREFOX_AUTOLAUNCH=1)."
  exit 0
fi

if ! command -v web-ext >/dev/null 2>&1; then
  echo "web-ext not on PATH — extension auto-load skipped."
  echo "    Install with: npm install --global web-ext  (or re-run bootstrap.sh)"
  echo "    Or load the extension manually via about:debugging."
  exit 0
fi

# If a previous web-ext is still alive, leave it alone — re-launching would
# just open another Firefox window pointed at the same profile.
if [ -f "$WEBEXT_PIDFILE" ] && kill -0 "$(cat "$WEBEXT_PIDFILE")" 2>/dev/null; then
  echo "Firefox (web-ext) already running — PID $(cat "$WEBEXT_PIDFILE"). Reusing."
  exit 0
fi

mkdir -p "$PROFILE_DIR"
echo "Launching Firefox with the extension preloaded…"
echo "Profile (persistent): $PROFILE_DIR"

# --keep-profile-changes: any IG login, cookies, bookmarks set in this Firefox
# window are preserved into $PROFILE_DIR so the next launch picks them up.
# --no-reload: don't watch the source dir for live-reload (we restart manually).
nohup web-ext run \
  --source-dir "$EXTENSION_DIR" \
  --firefox-profile "$PROFILE_DIR" \
  --keep-profile-changes \
  --no-reload \
  > /tmp/truth-analyzer-webext.log 2>&1 &
echo $! > "$WEBEXT_PIDFILE"
echo "Firefox launched (web-ext PID $(cat "$WEBEXT_PIDFILE")). Logs: tail -f /tmp/truth-analyzer-webext.log"
