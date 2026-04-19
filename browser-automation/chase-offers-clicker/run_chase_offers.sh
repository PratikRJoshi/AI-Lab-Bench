#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$SCRIPT_DIR/chase-offers-env/bin/activate"

python3 "$SCRIPT_DIR/chase_offers_clicker.py" || true

deactivate
