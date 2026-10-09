#!/usr/bin/env sh
set -eu

base_url="${1:-http://127.0.0.1:8000}"

python3 - "$base_url" <<'PY'
import json
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
for path in ("/health", "/ready", "/version"):
    with urllib.request.urlopen(base + path, timeout=10) as response:
        body = json.load(response)
        if response.status != 200:
            raise SystemExit(f"{path}: HTTP {response.status}")
        print(f"{path}: {json.dumps(body, sort_keys=True)}")
PY
