#!/usr/bin/env zsh
# claude-merge.sh
#
# Merges project-level .claude/settings.json permission entries up into the
# global ~/.claude/settings.json, then deletes the project-level file.
#
# Usage:
#   Run from any project root after a Claude Code session:
#     $ claude-merge
#
#   Or source this file in ~/.zshrc and call `claude-merge` directly.
#
# What it does:
#   - Scans for .claude/settings.json files under $PWD (up to 5 levels deep)
#   - Skips the global ~/.claude/settings.json
#   - Merges unique entries from `permissions.allow` and `permissions.allowedTools`
#     into the global settings file (deduplicates automatically)
#   - Deletes each project-level file after merging

claude-merge() {
  local global="$HOME/.claude/settings.json"
  local found=0

  if [[ ! -f "$global" ]]; then
    echo "ERROR: Global settings file not found at $global"
    return 1
  fi

  if ! command -v jq &>/dev/null; then
    echo "ERROR: jq is required but not installed. Run: brew install jq"
    return 1
  fi

  while IFS= read -r proj_file; do
    echo "Found project settings: $proj_file"

    local new_allows
    new_allows=$(jq -r '.permissions.allow[]? // empty' "$proj_file" 2>/dev/null)
    local new_tools
    new_tools=$(jq -r '.permissions.allowedTools[]? // empty' "$proj_file" 2>/dev/null)

    if [[ -n "$new_allows" ]]; then
      while IFS= read -r entry; do
        local exists
        exists=$(jq --arg e "$entry" '.permissions.allow | index($e)' "$global")
        if [[ "$exists" == "null" ]]; then
          echo "  Adding to allow: $entry"
          jq --arg e "$entry" '.permissions.allow += [$e]' "$global" > /tmp/claude_merge_tmp.json \
            && mv /tmp/claude_merge_tmp.json "$global"
        fi
      done <<< "$new_allows"
    fi

    if [[ -n "$new_tools" ]]; then
      while IFS= read -r entry; do
        local exists
        exists=$(jq --arg e "$entry" '.permissions.allowedTools | index($e)' "$global")
        if [[ "$exists" == "null" ]]; then
          echo "  Adding to allowedTools: $entry"
          jq --arg e "$entry" '.permissions.allowedTools += [$e]' "$global" > /tmp/claude_merge_tmp.json \
            && mv /tmp/claude_merge_tmp.json "$global"
        fi
      done <<< "$new_tools"
    fi

    echo "  Deleting $proj_file"
    rm "$proj_file"
    found=1
  done < <(find "$PWD" -maxdepth 5 -name "settings.json" -path "*/.claude/*" \
             -not -path "$HOME/.claude/*" 2>/dev/null)

  if [[ $found -eq 0 ]]; then
    echo "No project-level .claude/settings.json files found under $PWD"
  else
    echo "Done. Global settings updated: $global"
  fi
}
