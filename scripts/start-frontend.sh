#!/usr/bin/env bash
# DirCoMedia Next.js dashboard launcher for PM2.
set -euo pipefail
cd /home/vinta/dircomedia/frontend
exec npx next start --hostname 127.0.0.1 --port "${NEXT_PORT:-4601}"
