#!/usr/bin/env bash
# Claude Code Status Line
# Reads JSON from stdin (provided by Claude Code) and renders a colorized status bar.
#
# Output format:
#   DD/MM/YY HH:MM 🧠 Model Name | 👤 user | 🔥 NN% ▐████░░░░▌ NNNk | $X.XX
#
# Usage in ~/.claude/settings.json:
#   "statusLine": {
#     "type": "command",
#     "command": "~/.claude/scripts/claude-statusline.sh",
#     "padding": 0
#   }
#
# Bar color thresholds:
#   Green  < 50%  — plenty of context remaining
#   Yellow >= 50% — halfway through context window
#   Red    >= 80% — approaching compaction

input=$(cat)

# --- Metadata ---
user=$(whoami)
dt=$(date '+%d/%m/%y %H:%M')
model=$(echo "$input" | jq -r '.model.display_name')

# --- Token counts ---
tin=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
tout=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)
total_tokens=$((tin + tout))

if [ $total_tokens -ge 1000000 ]; then
  tokens_display=$(echo "scale=1; $total_tokens / 1000000" | bc)M
elif [ $total_tokens -ge 1000 ]; then
  tokens_display=$(echo "scale=1; $total_tokens / 1000" | bc)k
else
  tokens_display="${total_tokens}"
fi

# --- Cost calculation (per-model pricing: $/MTok) ---
inp=3.0; outp=15.0
[[ "$model" == *"Opus"* ]] && inp=15.0 && outp=75.0
[[ "$model" == *"Haiku"* ]] && inp=0.8 && outp=4.0

icost=$(echo "scale=2; $tin * $inp / 1000000" | bc)
ocost=$(echo "scale=2; $tout * $outp / 1000000" | bc)
tcost=$(echo "scale=2; $icost + $ocost" | bc)
cost=$(printf "%.2f" $tcost)

# --- Progress bar (20 chars wide, 1 block = 5%) ---
bar_width=20
filled=$((used_pct * bar_width / 100))
empty=$((bar_width - filled))

bar=''
i=0; while [ $i -lt $filled ]; do bar="${bar}█"; i=$((i+1)); done
i=0; while [ $i -lt $empty ];  do bar="${bar} "; i=$((i+1)); done

# --- ANSI colors ---
CYAN='\033[36m'
ORANGE='\033[38;5;208m'
GREEN='\033[32m'
YELLOW='\033[33m'
BRIGHT_YELLOW='\033[93m'
RED='\033[31m'
RESET='\033[0m'

# Bar color based on usage threshold
bar_color="${GREEN}"
[ $used_pct -ge 50 ] && bar_color="${YELLOW}"
[ $used_pct -ge 80 ] && bar_color="${RED}"

# --- Render ---
output="${CYAN}${dt}${RESET} 🧠 ${GREEN}${model}${RESET} | 👤 ${ORANGE}${user}${RESET} | 🔥 ${bar_color}${used_pct}%${RESET} ${bar_color}▐${bar}▌${RESET} ${BRIGHT_YELLOW}${tokens_display}${RESET}"
[ "$tcost" != "0" ] && [ -n "$tcost" ] && output="${output} | ${YELLOW}\$${cost}${RESET}"

printf "%b\n" "$output"
