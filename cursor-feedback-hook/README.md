# Cursor Feedback Dialog Hook

A macOS `stop` hook for Cursor IDE (and optionally Claude Code) that pops a lightweight feedback dialog after every agent response. Feedback is logged to a local JSONL file for later review.

## What it does

After each agent turn completes, a native macOS dialog appears with options:

- **too long** / **too vague** / **missed a detail** / **wrong** / **good - keep this**

If you select a negative flag, a follow-up dialog optionally captures a one-line correction.

When multiple chat sessions are running, the dialog title shows the Cursor chat name (e.g., `[Job role at Sift] Rate answer`) so you can tell which session it refers to.

All feedback is appended to `~/.concise-observer/feedback.jsonl` with timestamp, tool, flags, the last Q/A pair, and an optional correction.

## Prerequisites

- **macOS** (uses `osascript` for native dialogs)
- `jq` -- `brew install jq`
- `python3` -- ships with macOS or `brew install python3`
- `sqlite3` -- ships with macOS

## Install

```bash
git clone https://github.com/PratikRJoshi/AI-Lab-Bench.git
cd AI-Lab-Bench/cursor-feedback-hook
./install.sh
```

The installer:
1. Copies `rate-dialog.sh` to `~/.concise-observer/`
2. Merges a `stop` hook entry into `~/.cursor/hooks.json` (creates the file if missing, appends without clobbering existing hooks)
3. Optionally wires the hook for Claude Code (`~/.claude/settings.json`)

Re-running `install.sh` is safe -- it skips if the hook is already wired.

## Uninstall

```bash
# Remove the hook entry from Cursor
jq 'del(.hooks.stop[] | select(.command | contains("rate-dialog.sh")))' \
  ~/.cursor/hooks.json > /tmp/hooks-clean.json && mv /tmp/hooks-clean.json ~/.cursor/hooks.json

# Remove the script and logs
rm -rf ~/.concise-observer
```

## Customizing feedback options

Edit the `opts` list in `rate-dialog.sh` (line with `set opts to`) to change the checkbox labels. The flags are stored verbatim in the JSONL log.

## How the chat title works

The dialog title shows the Cursor chat name by looking up the agent ID in Cursor's internal `state.vscdb` database (`composer.composerHeaders`). If the lookup fails (non-Cursor tool, DB not found), it falls back to the generic title "Rate the last answer".

## Feedback log format

Each line in `~/.concise-observer/feedback.jsonl`:

```json
{
  "ts": "2026-05-31T21:41:00Z",
  "tool": "cursor",
  "transcript": "/path/to/transcript.jsonl",
  "flags": ["too long", "missed a detail"],
  "question": "truncated last user message...",
  "answer": "truncated last assistant message...",
  "correction": "optional one-line correction"
}
```
