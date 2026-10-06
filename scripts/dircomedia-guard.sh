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

# Single-instance: never let two guards race to spawn the stack.
exec 9>"$LOCK" || exit 0
flock -n 9 || exit 0

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
    pm2 jlist 2>/dev/null | node -e '
        let d="";process.stdin.on("data",c=>d+=c);
        process.stdin.on("end",()=>{
            let want=process.argv[1];
            try{let a=JSON.parse(d);
                let p=a.find(x=>x.name===want);
                process.exit(p && p.pm2_env && p.pm2_env.status==="online" ? 0 : 1);
            }catch(e){process.exit(1);}
        });' "$1"
}

# ── THE REAL HEALTH CHECK ── returns 0 only if EVERYTHING is healthy.
# Prints the first failing reason to stdout for the caller to log.
all_healthy() {
    local svc code
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
pm2 start "$ECOSYSTEM" --update-env >/dev/null 2>&1
# Any service that existed-but-was-stopped/errored gets an explicit restart
# ('pm2 start <ecosystem>' only (re)starts entries it does not see as online).
for svc in $SERVICES; do
    if ! pm2_online "$svc"; then
        pm2 restart "$svc" --update-env >/dev/null 2>&1
    fi
done

# RE-CEMENT the dump so a reboot (or another watchdog's save during a future
# outage) can no longer lose dircomedia. This is the half that breaks the
# recurring-regression loop.
pm2 save >/dev/null 2>&1
log "pm2 save issued — dircomedia re-cemented into dump.pm2"

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
