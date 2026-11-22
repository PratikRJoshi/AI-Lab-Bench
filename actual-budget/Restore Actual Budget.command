#!/bin/bash
cd "$(dirname "$0")" || exit 1
/bin/bash ./restore.sh --install-deps
status=$?
echo
read -r -p "Press Enter to close this window. " _
exit "$status"
