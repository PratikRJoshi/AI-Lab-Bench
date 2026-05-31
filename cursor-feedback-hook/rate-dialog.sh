#!/bin/bash
# Auto-pop checkbox feedback dialog after an answer.
# Wired as a user-level Cursor `stop` hook (and Claude Code `Stop` hook in Phase 2).
# Design goals:
#   - Fail-open ALWAYS: never block or fail the agent turn.
#   - Non-blocking: backgrounds itself and returns immediately so the turn never stalls.
#   - Recursion-guarded: the headless observer's own LLM calls must not re-pop this dialog.
set -u

OBS_DIR="$HOME/.concise-observer"
LOG="$OBS_DIR/feedback.jsonl"
LOCKDIR="$OBS_DIR/.dialog.lock"
mkdir -p "$OBS_DIR"

# --- Recursion guard -------------------------------------------------------
# When our observer runs a headless agent it exports CONCISE_OBSERVER=1.
# Any hook firing under that environment must do nothing.
if [ "${CONCISE_OBSERVER:-}" = "1" ]; then exit 0; fi

# --- Stage 1: front (hook) process -----------------------------------------
# Consume stdin (hook JSON), hand it to a detached worker, return instantly.
if [ "${1:-}" != "--worker" ]; then
  input="$(cat 2>/dev/null || true)"
  CONCISE_INPUT="$input" nohup "$0" --worker >/dev/null 2>&1 &
  exit 0
fi

# --- Stage 2: detached worker ----------------------------------------------
# Clear a stale lock left by a killed worker (older than 10 min) so a leaked
# lock can never block dialogs forever.
if [ -d "$LOCKDIR" ] && [ -n "$(find "$LOCKDIR" -prune -mmin +10 2>/dev/null)" ]; then
  rmdir "$LOCKDIR" 2>/dev/null
fi
# Single-dialog lock: if one is already open, skip this turn.
if ! mkdir "$LOCKDIR" 2>/dev/null; then exit 0; fi
trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT

input="${CONCISE_INPUT:-}"
tool="cursor"
transcript=""

if [ -n "$input" ]; then
  transcript="$(printf '%s' "$input" | jq -r '.transcript_path // .transcriptPath // empty' 2>/dev/null || true)"
  if printf '%s' "$input" | jq -e '.hook_event_name // empty' >/dev/null 2>&1; then
    tool="claude"
  fi
fi

# Fallback: newest Cursor transcript across ALL workspaces (covers the common
# case where the stop hook does not pass a transcript path).
if [ -z "$transcript" ] || [ ! -f "$transcript" ]; then
  transcript="$(find "$HOME/.cursor/projects" -type f -name '*.jsonl' -path '*/agent-transcripts/*' 2>/dev/null | xargs ls -t 2>/dev/null | head -1)"
fi
[ -f "$transcript" ] || exit 0

# --- Extract last Q / A ----------------------------------------------------
# NOTE: take the last RECORD (JSONL is one object per line), not the last
# physical line of a multi-line message.
raw_q="$(jq -rc 'select(.role=="user")' "$transcript" 2>/dev/null | tail -1 | jq -r '[.message.content[]?|select(.type=="text")|.text]|join("\n")' 2>/dev/null)"
# Prefer the inner <user_query> payload when present.
question="$(printf '%s' "$raw_q" | perl -0777 -ne 'if (/<user_query>\s*(.*?)\s*<\/user_query>/s){print $1}else{print $_}' 2>/dev/null)"
[ -n "$question" ] || question="$raw_q"
question="$(printf '%s' "$question" | cut -c1-800)"

answer="$(jq -rc 'select(.role=="assistant")' "$transcript" 2>/dev/null | tail -1 | jq -r '[.message.content[]?|select(.type=="text")|.text]|join("\n")' 2>/dev/null | cut -c1-1800)"

# --- Derive chat title for the dialog title -------------------------------
session_label=""
if [ -n "$transcript" ]; then
  agent_id="$(basename "$(dirname "$transcript")" 2>/dev/null)"
  if [ -n "$agent_id" ]; then
    STATE_DB="$HOME/Library/Application Support/Cursor/User/globalStorage/state.vscdb"
    if [ -f "$STATE_DB" ]; then
      session_label="$(sqlite3 "$STATE_DB" "SELECT value FROM ItemTable WHERE key='composer.composerHeaders';" 2>/dev/null \
        | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    for c in data.get('allComposers', []):
        if c.get('composerId') == '$agent_id':
            n = c.get('name', '')
            if n and n != 'N/A':
                print(n[:80])
            break
except: pass
" 2>/dev/null)"
    fi
  fi
fi
dialog_title="Rate the last answer"
[ -n "$session_label" ] && dialog_title="[$session_label] Rate answer"

# --- Checkbox dialog (no TTY needed) ---------------------------------------
# Use -e flags (not a here-doc): macOS /bin/bash is 3.2 and mis-parses here-docs
# inside $(), especially the apostrophe in "AppleScript's". "my text item
# delimiters" avoids that apostrophe entirely.
sel="$(osascript \
  -e 'set opts to {"too long", "too vague", "missed a detail", "wrong", "good - keep this"}' \
  -e "set choice to choose from list opts with title \"$dialog_title\" with prompt \"How did this answer fall short? (pick any; Cancel = skip)\" with multiple selections allowed and empty selection allowed" \
  -e 'if choice is false then return "__SKIP__"' \
  -e 'set my text item delimiters to "|"' \
  -e 'return choice as text' 2>/dev/null)"

# Skipped or nothing selected -> log nothing, exit clean.
case "$sel" in
  ""|"__SKIP__") exit 0 ;;
esac

# --- Optional one-line correction for negative flags -----------------------
correction=""
case "$sel" in
  *wrong*|*"missed a detail"*|*"too long"*|*"too vague"*)
    correction="$(osascript \
  -e 'try' \
  -e 'set r to display dialog "Optional: what should it have said? (OK to skip)" default answer "" with title "Correction" buttons {"Skip","Save"} default button "Save" giving up after 60' \
  -e 'if button returned of r is "Save" then return text returned of r' \
  -e 'end try' \
  -e 'return ""' 2>/dev/null)"
  ;;
esac

# --- Append one JSONL feedback record --------------------------------------
jq -nc \
  --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg tool "$tool" \
  --arg flags "$sel" \
  --arg q "$question" \
  --arg a "$answer" \
  --arg c "$correction" \
  --arg t "$transcript" \
  '{ts:$ts, tool:$tool, transcript:$t, flags:($flags|split("|")|map(select(length>0))), question:$q, answer:$a, correction:$c}' \
  >> "$LOG" 2>/dev/null

# --- Kick the per-turn observer (detached, recursion-guarded) --------------
if [ -x "$OBS_DIR/observe.sh" ]; then
  CONCISE_OBSERVER=1 nohup "$OBS_DIR/observe.sh" >/dev/null 2>&1 &
fi

exit 0
