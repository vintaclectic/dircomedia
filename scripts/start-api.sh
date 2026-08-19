#!/usr/bin/env bash
# DirCoMedia FastAPI launcher for PM2.
# WHY a script: pm2 hands a bare `uvicorn` console-script to Node, which chokes on
# the Python shebang ("SyntaxError: Invalid or unexpected token"). Invoking
# `python3 -m uvicorn` from a shell wrapper sidesteps interpreter guessing entirely.
set -euo pipefail
cd /home/vinta/dircomedia/backend
exec python3 -m uvicorn app.main:app --host 127.0.0.1 --port "${API_PORT:-8000}"
