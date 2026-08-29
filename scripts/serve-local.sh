#!/bin/bash
# Local-only preview of the Intel Analysis Wiki (generated docs/).
# Serves on 127.0.0.1:8043 — not reachable outside this Mac.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ ! -f docs/index.html ]; then
  echo "docs/index.html not found — run the build first:" >&2
  echo "  ~/.hermes/hermes-agent/venv/bin/python3 scripts/build_site.py" >&2
  exit 1
fi
echo "Serving $ROOT/docs on http://127.0.0.1:8043  (Ctrl-C to stop)"
exec python3 -m http.server 8043 --directory docs --bind 127.0.0.1