#!/usr/bin/env bash
# Start the Truth Analyzer backend server using the virtual environment.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "truth-analyzer-env" ]; then
  echo "Virtual environment not found. Run ./setup.sh first."
  exit 1
fi

# Kill any existing instance
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
