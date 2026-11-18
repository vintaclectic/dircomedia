#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# DirCoMedia — SELF-HEALING GUARD            (installed 2026-10-06, task TWXCVMS)
#
# WHY THIS EXISTS — the third regression (after YXCZ8ZM, ZBG52ZY):
# DirCoMedia kept vanishing from PM2 and never came back on its own. The
# root cause, MEASURED 2026-10-06:
#   1. The box rebooted 2026-10-02 06:53. dircomedia-* ran until 06:51
#      (last stdout write) and then never restarted, because `pm2
#      resurrect` restores from ~/.pm2/dump.pm2 and that dump did not
#      contain the dircomedia entries.
#   2. DirCoMedia was the ONLY major stack with no self-healing guard.
#      dirhaven has tunnel-guard + backend-health-guard; vintinuum has
#      keepalive + watchdog-daemon — all of which RE-CREATE their missing
#      PM2 entries. DirCoMedia had nothing, so once it fell out of PM2 it
#      stayed out.
#   3. A dozen other watchdogs run a bare `pm2 save` whenever THEIR own
#      service needs recovery (vintinuum-keepalive, dirhaven-tunnel-guard,
#      watchdog-daemon, the ollama recovery path). Every such save captures
#      the live process set at that instant — which, with dircomedia down,
#      PERMANENTLY erased it from the resurrect source. That is the exact
#      "dump.pm2 overwritten by a save taken during an outage" footgun
#      ZBG52ZY recorded.
#
# WHAT THIS GUARD DOES — the fix:
#   * The ecosystem file is the SOURCE OF TRUTH, never the dump. This guard
#     restores every missing/stopped dircomedia service from
#     ecosystem.config.js (handles BOTH stopped AND fully-deleted entries,
#     because `pm2 start <ecosystem>` creates the absent ones and restarts
#     the stopped ones; already-online ones are skipped).
#   * After any restore it runs `pm2 save`, which RE-CEMENTS dircomedia back
#     into dump.pm2 — so even if another watchdog's save had dropped it, the
#     dump self-heals within one guard interval.
#   * Health is proven by ACTUAL HTTP against the four public ports
#     (8000/health, 4600, 4601, 4699) AND by PM2 presence of all seven
#     services — never by process existence alone.
#
# HEALTH CHECK IS TESTED AGAINST A DEAD TARGET (liveness-probe lesson
# M7FARQP): all_healthy() returns NON-ZERO the moment any port stops
# answering 200 or any of the seven services is missing/not-online. A curl
# that times out yields a non-2xx code that is normalized to 000 and scored
# as FAIL — never silently passed.
#
# Wiring (crontab): */2 * * * *  + @reboot sleep 60
# ═══════════════════════════════════════════════════════════════════════
set -uo pipefail

ECOSYSTEM="/home/vinta/dircomedia/ecosystem.config.js"
LOG="/home/vinta/.dircomedia-guard.log"
STATE="/home/vinta/.dircomedia-guard.state"
LOCK="/home/vinta/.dircomedia-guard.lock"
MAX_LOG_BYTES=2000000

# The seven services declared in ecosystem.config.js — all must be online.
SERVICES="dircomedia-api dircomedia-frontend dircomedia-gateway dircomedia-shim dircomedia-beat dircomedia-worker dircomedia-tunnel"

export NVM_DIR="/home/vinta/.nvm"
# shellcheck disable=SC1091
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" >/dev/null 2>&1
export PATH="$PATH:/usr/local/bin:/usr/bin:/home/vinta/.nvm/versions/node/$(ls -1 /home/vinta/.nvm/versions/node 2>/dev/null | tail -1)/bin"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

# == Single-instance, but NEVER silently forever (MWNMNT9, 2026-11-18) ==
# MEASURED 2026-11-18 00:4x: the lock file's mtime was 2026-11-18 00:08 (so
# `exec 9>"$LOCK"` HAD run that tick) while this guard's log's last line was
# 2026-11-16 06:51:26 -- and every code path below this block calls log().
# Enumerated, the only exits above the first log() were these two lines, so
# the guard had been exiting at `flock -n` for ~2 days while all seven
# services sat `stopped` and :8000 answered 000 (control :8798 -> 200).
# A silent `exit 0` on a busy lock converts ONE wedged holder into a
# PERMANENT outage of the self-healing guard itself -- strictly worse than
# having no guard, because `pm2 list` still shows the entries and nothing
# anywhere says the watchdog stood down.
# fd 9 is inherited by every child, and `pm2 start` spawns the God Daemon
# detached, so a single long-lived descendant of an earlier run holds this
# lock for its entire life. Three changes, each independently load-bearing:
#   (1) spawn with `9>&-` so no child can ever inherit the lock again;
#   (2) shout (rate-limited, never muted) whenever the lock is busy;
#   (3) break a lock held longer than any real guard run can possibly take.
STALE_LOCK_SECS=900   # guard worst case ~5.5 min: 4 curls@6s + 60s + 7x30s + 15x4s
NAG_SECS=900          # throttle a REFUSAL; never silence it (5WM3QQX)

BUSY_STAMP="${LOCK}.busy-since"
NAG_STAMP="${LOCK}.nagged-at"

_now() { date +%s; }
# Age in seconds of the unix stamp in $1; -1 when absent/garbage.
_age() {
    local t
    t=$(cat "$1" 2>/dev/null)
    case "$t" in ''|*[!0-9]*) echo -1 ;; *) echo $(( $(_now) - t )) ;; esac
}
# log() at most once per NAG_SECS. A refusal may be throttled, never muted.
nag() {
    local age
    age=$(_age "$NAG_STAMP")
    if [ "$age" -lt 0 ] || [ "$age" -ge "$NAG_SECS" ]; then
        log "$*"
        _now > "$NAG_STAMP" 2>/dev/null || true
    fi
}

exec 9>"$LOCK" || { log "FATAL: cannot open lock $LOCK -- guard cannot run"; exit 1; }

if ! flock -n 9; then
    [ -f "$BUSY_STAMP" ] || _now > "$BUSY_STAMP" 2>/dev/null || true
    busy_for=$(_age "$BUSY_STAMP")
    [ "$busy_for" -lt 0 ] && busy_for=0
    if [ "$busy_for" -ge "$STALE_LOCK_SECS" ]; then
        log "STALE LOCK -- $LOCK busy ${busy_for}s (> ${STALE_LOCK_SECS}s, longer than any real guard run); breaking it onto a fresh inode"
        rm -f "$LOCK" "$BUSY_STAMP" 2>/dev/null || true
        exec 9>"$LOCK" || { log "FATAL: cannot re-open lock after break"; exit 1; }
        flock -n 9 || { log "FATAL: lock still busy immediately after break -- standing down"; exit 1; }
        log "stale lock broken -- proceeding with the health check"
    else
        nag "lock busy ${busy_for}s (an earlier guard run or one of its children holds $LOCK) -- skipping this tick; breaking it at ${STALE_LOCK_SECS}s"
        exit 0
    fi
fi
rm -f "$BUSY_STAMP" 2>/dev/null || true

# Rotate our own log so this never becomes the next disk problem.
if [ -f "$LOG" ] && [ "$(stat -c%s "$LOG" 2>/dev/null || echo 0)" -gt "$MAX_LOG_BYTES" ]; then
    mv -f "$LOG" "${LOG}.1" 2>/dev/null
fi

# ── Probe one URL; echo a normalized 3-digit code (000 on any failure) ──
http_code() {
    local url="$1" code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 6 "$url" 2>/dev/null)
    case "$code" in [1-5][0-9][0-9]) ;; *) code=000 ;; esac
    echo "$code"
}

# ── Is a PM2 process present AND online? ──
pm2_online() {
    printf '%s' "$JL" | node -e '
        let d="";process.stdin.on("data",c=>d+=c);
        process.stdin.on("end",()=>{
            let want=process.argv[1];
            try{let a=JSON.parse(d);
                let p=a.find(x=>x.name===want);
                process.exit(p && p.pm2_env && p.pm2_env.status==="online" ? 0 : 1);
            }catch(e){process.exit(1);}
        });' "$1" 9>&-
}

# ── THE REAL HEALTH CHECK ── returns 0 only if EVERYTHING is healthy.
# Prints the first failing reason to stdout for the caller to log.
all_healthy() {
    local svc code
    # One bounded jlist per check (was one unbounded call per service — 7 hung
    # clients per run when PM2 stalled). PILEUP-2026-10-26
    JL=$(timeout 20 pm2 jlist 2>/dev/null 9>&-)
    for svc in $SERVICES; do
        if ! pm2_online "$svc"; then
            echo "pm2 service '$svc' missing or not online"
            return 1
        fi
    done
    code=$(http_code "http://127.0.0.1:8000/health")
    [ "$code" = "200" ] || { echo "api :8000/health -> $code"; return 1; }
    code=$(http_code "http://127.0.0.1:4601/")
    [ "$code" = "200" ] || { echo "frontend :4601/ -> $code"; return 1; }
    code=$(http_code "http://127.0.0.1:4600/")
    [ "$code" = "200" ] || { echo "gateway :4600/ -> $code"; return 1; }
    code=$(http_code "http://127.0.0.1:4699/")
    [ "$code" = "200" ] || { echo "shim :4699/ -> $code"; return 1; }
    return 0
}

# ── PILEUP-2026-10-26: PM2 itself unresponsive? Then do NOTHING. ──
# Restarting through a stalled/split daemon is what orphaned 198 celery
# processes (17GB). A dead daemon is vintinuum-keepalive's job, not ours.
if ! pgrep -f 'PM2 v[0-9.]*: God Daemon' >/dev/null || ! timeout 15 pm2 ping >/dev/null 2>&1 9>&-; then
    nag "PM2 daemon absent/unresponsive — skipping (not restarting through a broken PM2)"
    echo "pm2_unresponsive $(date +%s)" > "$STATE"
    exit 0
fi

# ── Healthy? record and leave. ──
REASON="$(all_healthy)" && { echo "ok $(date +%s)" > "$STATE"; exit 0; }

log "HEALTH CHECK FAILED — $REASON"

if ! command -v pm2 >/dev/null 2>&1; then
    log "FATAL: pm2 not on PATH — cannot manage the stack"
    echo "no_pm2 $(date +%s)" > "$STATE"
    exit 1
fi

# ── Restore from the SOURCE OF TRUTH (handles deleted AND stopped) ──
log "restoring dircomedia stack from ecosystem.config.js"
# Reap celery orphaned by earlier restarts before adding new ones (PILEUP-2026-10-26).
_orph=$(ps -eo pid=,ppid=,args= | awk '$2==1 && /celery -A app.workers.celery_app/ {print $1}')
[ -n "$_orph" ] && { kill $_orph 2>/dev/null; log "reaped orphaned celery: $(echo $_orph | wc -w)"; }
timeout 60 pm2 start "$ECOSYSTEM" --update-env >/dev/null 2>&1 9>&-
# Any service that existed-but-was-stopped/errored gets an explicit restart
# ('pm2 start <ecosystem>' only (re)starts entries it does not see as online).
for svc in $SERVICES; do
    if ! pm2_online "$svc"; then
        timeout 30 pm2 restart "$svc" --update-env >/dev/null 2>&1 9>&-
    fi
done

# RE-CEMENT the dump so a reboot (or another watchdog's save during a future
# outage) can no longer lose dircomedia. This is the half that breaks the
# recurring-regression loop.
# 2026-10-18: through the shared guard — a bare save here, during a partial boot,
# re-cemented dircomedia AND cemented the absence of everything else.
if bash /home/vinta/vintinuum-api/scripts/pm2-safe-save.sh --reason "dircomedia-guard" >/dev/null 2>&1 9>&-; then
    log "pm2 save issued — dircomedia re-cemented into dump.pm2"
else
    log "pm2 save REFUSED by pm2-safe-save (live list lacks apps the dump has) — dump left intact"
fi

# ── Verify the repair actually worked; never claim success blindly ──
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    sleep 4
    if REASON="$(all_healthy)"; then
        log "RECOVERED — all 7 services online and 4 ports answering after ${i} check(s)"
        echo "recovered $(date +%s)" > "$STATE"
        exit 0
    fi
done

log "RECOVERY INCOMPLETE after ~60s — last failing: $REASON"
log "  diagnose: pm2 logs dircomedia-api --lines 40 ; tail ~/.pm2/logs/dircomedia-frontend-error.log"
echo "failed $(date +%s)" > "$STATE"
exit 1
