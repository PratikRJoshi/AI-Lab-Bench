#!/usr/bin/env bash
# Run once to create the virtual environment and install all dependencies.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Installing dependencies..."
truth-analyzer-env/bin/pip install --upgrade pip
truth-analyzer-env/bin/pip install -r requirements.txt boto3

echo ""
echo "Setup complete."
echo "To start the server:  ./start.sh"
echo "To refresh AWS creds: ./refresh.sh"
