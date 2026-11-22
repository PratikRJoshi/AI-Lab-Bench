#!/bin/bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$(dirname "$0")"
if [[ "${1:-}" == "--install-deps" ]]; then
  shift
  if [[ "$(uname -s)" != Darwin ]]; then
    echo "Install Python 3.9+, GnuPG 2, GitHub CLI and Docker Compose, then run ./restore.sh."
    exit 1
  fi
  if ! command -v brew >/dev/null; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  fi
  for pair in 'python3:python' 'gpg:gnupg' 'gh:gh'; do
    command -v "${pair%%:*}" >/dev/null || brew install "${pair#*:}"
  done
  if ! command -v docker >/dev/null; then
    brew install --cask docker-desktop
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Opening Docker Desktop; finish any first-run prompts in its window."
    open -a Docker
    ready=0
    for ((i=0; i<150; i++)); do
      if docker info >/dev/null 2>&1; then ready=1; break; fi
      sleep 2
    done
    [[ "$ready" == 1 ]] || { echo "Start Docker Desktop, then rerun ./restore.sh."; exit 1; }
  fi
fi
exec python3 budget_recovery.py restore "$@"

