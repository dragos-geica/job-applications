#!/bin/bash
# Run with: bash start.command (also works with the Mac's built-in Bash 3.2).
set -euo pipefail
cd "$(dirname "$0")"

if [ -x .venv/bin/python ]; then
    python_bin=.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then
    python_bin=python3
else
    echo 'Python is missing. Install Python 3.12 from https://www.python.org/downloads/macos/ then try again.'
    exit 1
fi
if ! "$python_bin" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo 'Northbound needs Python 3.9 or newer. No app files or personal data were changed.'
    echo 'Install Python 3.12 from python.org and create a new virtual environment with it.'
    exit 1
fi
"$python_bin" --version
if [ ! -x .venv/bin/python ]; then
    "$python_bin" -m venv .venv
fi
# Stop here on installation failure. Never proceed to password/research/startup.
.venv/bin/python -m pip install -r requirements.lock
if [ ! -s data/password.hash ]; then
    .venv/bin/python app.py --set-password
fi
if [ ! -f data/.initial-research ]; then
    echo 'Checking initial research sources. This may take a few minutes...'
    .venv/bin/python seed_research.py
    .venv/bin/python research.py --once
    touch data/.initial-research
fi
worker_pid=''
cleanup() {
    if [ -n "$worker_pid" ]; then
        kill "$worker_pid" 2>/dev/null || true
        wait "$worker_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
.venv/bin/python research.py &
worker_pid=$!
echo ''
echo 'Open http://127.0.0.1:8000 in Safari or Chrome on this Mac.'
echo 'Leave this window open. Press Control+C to stop the app and research worker.'
.venv/bin/python app.py
