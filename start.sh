#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-$(python3 -c 'import socket
for p in range(8000, 8050):
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", p)) != 0:
            print(p); break')}"
echo "Starting FMPO S7 MedPrep Studio on http://127.0.0.1:${PORT} ..."
exec python3 -m uvicorn backend.app:app --host 127.0.0.1 --port "${PORT}"
