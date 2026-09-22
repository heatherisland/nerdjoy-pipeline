#!/bin/bash
# launchd entry point. Waits briefly so the CSV and MANIFEST both land.
cd "$(dirname "$0")/.." || exit 1
sleep 15
exec .venv/bin/python scripts/refresh.py "$@"
