#!/usr/bin/env bash
# DirCoMedia Celery BEAT launcher for PM2 (ZBG52ZY, 2026-08-27).
#
# WHY this exists: celery_app.py has defined a full beat_schedule for weeks —
# process_due_schedules every 60s, OAuth token refresh every 6h, analytics
# hourly, the persistence engine daily — and NOTHING WAS RUNNING IT. The
# ecosystem file declared six processes and a beat scheduler was not among
# them, while the worker's own comment claimed it carried "the beat guardians".
# It never did: start-worker.sh runs `celery worker`, which consumes tasks but
# never ENQUEUES scheduled ones.
#
# The blast radius of that omission is the whole product:
#   - scheduled posts never published (process_due_schedules never fired)
#   - OAuth tokens were never refreshed, so they silently expired — which is
#     exactly how X/Instagram/Pinterest rotted out from under the dashboard
#   - analytics never collected, so the strategy engine learned from nothing
# It reads as "approved post never went out" rather than an outage: the silent
# failure the worker comment warned about, caused by the missing half of it.
#
# Same bash-wrapper reason as start-worker.sh: pm2 hands a bare `celery`
# console-script to Node, which chokes on the Python shebang while still
# reporting `online` — a silent outage. `python3 -m celery` avoids that.
#
# ONE beat, ever. Two beat processes double-fire every scheduled post, so this
# must never be scaled past a single instance.
set -euo pipefail
cd /home/vinta/dircomedia/backend
# PILEUP-2026-10-26: guarantee a single celery beat. Reap any beat orphaned
# to init by an earlier restart, then hold an exclusive lock that the python
# process inherits through exec (PM2 signals python directly, so the lock dies
# with it). A second beat cannot start while one is alive.
for _p in $(ps -eo pid=,ppid=,args= | awk '$2==1 && /celery -A app.workers.celery_app beat/ {print $1}'); do
  kill "$_p" 2>/dev/null || true
done
exec 7>/home/vinta/dircomedia/backend/.celery-beat.lock
flock -w 15 7 || { echo "another celery beat holds the lock — refusing to start a duplicate" >&2; exit 1; }
exec python3 -m celery -A app.workers.celery_app beat \
  --loglevel=info \
  --schedule=/home/vinta/dircomedia/backend/celerybeat-schedule
