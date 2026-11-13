#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${S7_DATA_DIR:-/app/data}"
SEED_DIR="/app/seed_data"

mkdir -p "$DATA_DIR"

if [ -d "$SEED_DIR" ]; then
  python3 - "$SEED_DIR" "$DATA_DIR" <<'PY'
import shutil
import sys
from pathlib import Path

seed_root = Path(sys.argv[1])
data_root = Path(sys.argv[2])
copied = 0
for src in seed_root.rglob("*"):
    rel = src.relative_to(seed_root)
    dst = data_root / rel
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
    elif not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
if copied:
    print(f"Seeded {copied} missing file(s) into {data_root}", flush=True)
PY
fi

exec python3 -m uvicorn backend.app:app --host 0.0.0.0 --port "${PORT:-8000}"
