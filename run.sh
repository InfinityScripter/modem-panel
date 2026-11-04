#!/bin/sh
# Creates a local venv on first run, then starts the panel.
set -e
cd "$(dirname "$0")"
if [ ! -e /opt/homebrew/lib/libusb-1.0.dylib ] && [ ! -e /usr/local/lib/libusb-1.0.dylib ]; then
  echo "Нужен libusb: brew install libusb"; exit 1
fi
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
exec .venv/bin/python3 server.py "$@"
