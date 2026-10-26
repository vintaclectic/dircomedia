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
# PILEUP-2026-10-26: guarantee a single celery worker. Reap any worker orphaned
# to init by an earlier restart, then hold an exclusive lock that the python
# process inherits through exec (PM2 signals python directly, so the lock dies
# with it). A second worker cannot start while one is alive.
for _p in $(ps -eo pid=,ppid=,args= | awk '$2==1 && /celery -A app.workers.celery_app worker/ {print $1}'); do
  kill "$_p" 2>/dev/null || true
done
exec 7>/home/vinta/dircomedia/backend/.celery-worker.lock
flock -w 15 7 || { echo "another celery worker holds the lock — refusing to start a duplicate" >&2; exit 1; }
exec python3 -m celery -A app.workers.celery_app worker \
  -Q "${CELERY_QUEUES:-content,video,distribution}" \
  -c "${CELERY_CONCURRENCY:-2}" \
  --loglevel=info
