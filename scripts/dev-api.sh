#!/usr/bin/env bash
# Run the API on 127.0.0.1:8000 from this checkout.
set -euo pipefail
cd "$(dirname "$0")/../backend"
exec .venv/bin/uvicorn cpsc360.app:app --host 127.0.0.1 --port 8000 "$@"
