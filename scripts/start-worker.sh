#!/usr/bin/env bash
# DirCoMedia Celery worker launcher for PM2.
#
# WHY a script (same reason as start-api.sh): pm2 hands a bare `celery`
# console-script to Node, which chokes on the Python shebang
# ("SyntaxError: Invalid or unexpected token") while still reporting `online` —
# a silent outage. `python3 -m celery` from a shell wrapper avoids all
# interpreter guessing.
#
# ONE worker, THREE queues. docker-compose.yml splits content/video/
# distribution across three containers for horizontal scale; on this single box
# that would be three idle processes competing for the same Redis. One worker
# consuming all three queues is the same fan-out at a quarter of the memory —
# and it is what the docs call `dircomedia-worker` (singular).
set -euo pipefail
cd /home/vinta/dircomedia/backend
exec python3 -m celery -A app.workers.celery_app worker \
  -Q "${CELERY_QUEUES:-content,video,distribution}" \
  -c "${CELERY_CONCURRENCY:-2}" \
  --loglevel=info
