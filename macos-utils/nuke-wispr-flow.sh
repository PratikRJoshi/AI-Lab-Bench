#!/usr/bin/env bash
set -euo pipefail

deleted=()
skipped=()

echo "=== Nuking Wispr Flow ==="

if pkill -f "Wispr Flow" 2>/dev/null; then
  deleted+=("Wispr Flow processes")
fi

if launchctl remove com.electron.wispr-flow.ShipIt 2>/dev/null; then
  deleted+=("Launch agent: com.electron.wispr-flow.ShipIt")
fi

targets=(
  "$HOME/Library/Application Support/Wispr Flow"
  "$HOME/Library/Caches/com.electron.wispr-flow"
  "$HOME/Library/Caches/com.electron.wispr-flow.ShipIt"
  "$HOME/Library/Caches/com.electron.wispr-flow.accessibility-mac-app"
  "$HOME/Library/Preferences/com.electron.wispr-flow.plist"
  "$HOME/Library/Logs/Wispr Flow"
  "$HOME/Library/HTTPStorages/com.electron.wispr-flow"
  "$HOME/Library/Saved Application State/com.electron.wispr-flow.savedState"
  "$HOME/Library/Containers/com.electron.wispr-flow"
  "$HOME/Library/Group Containers/com.electron.wispr-flow"
  "/Applications/Wispr Flow.app"
  "$HOME/Applications/Wispr Flow.app"
)

for t in "${targets[@]}"; do
  if [ -e "$t" ]; then
    rm -rf "$t"
    deleted+=("$t")
  else
    skipped+=("$t")
  fi
done

while IFS= read -r f; do
  [ -z "$f" ] && continue
  rm -f "$f"
  deleted+=("$f")
done < <(find "$HOME/Downloads" -maxdepth 1 -iname "Flow-*.dmg" 2>/dev/null)

clean_firefox=true
if pgrep -x "firefox" >/dev/null 2>&1; then
  echo ""
  echo "Firefox is currently running."
  read -rp "Close Firefox and clear site data? [y/N]: " answer
  if [[ "$answer" =~ ^[Yy]$ ]]; then
    pkill -x "firefox" 2>/dev/null
    sleep 2
  else
    clean_firefox=false
    skipped+=("Firefox site data (user skipped)")
  fi
fi

if $clean_firefox; then
  for profile_dir in "$HOME/Library/Application Support/Firefox/Profiles"/*/; do
    for site in "https+++wisprflow.ai" "https+++docs.wisprflow.ai"; do
      target="$profile_dir/storage/default/$site"
      if [ -d "$target" ]; then
        rm -rf "$target"
        deleted+=("Firefox: $site (${profile_dir##*/})")
      fi
    done
  done
fi

echo ""
echo "=== Summary ==="
echo ""
if [ ${#deleted[@]} -gt 0 ]; then
  echo "CLEARED (${#deleted[@]}):"
  for item in "${deleted[@]}"; do
    echo "  ✓ $item"
  done
else
  echo "Nothing to clear — Wispr Flow is already gone."
fi

if [ ${#skipped[@]} -gt 0 ]; then
  echo ""
  echo "NOT FOUND / SKIPPED (${#skipped[@]}):"
  for item in "${skipped[@]}"; do
    echo "  - $item"
  done
fi

echo ""
echo "=== Done ==="
