#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# verify-guard-lock-MWNMNT9.sh — dircomedia-guard.sh single-instance lock
#
# WHY THIS EXISTS (measured 2026-11-18, card MWNMNT9):
#   All seven dircomedia services sat `stopped` (pid 0) and :8000 answered 000
#   for ~2 days while ~/.dircomedia-guard.log's last line was 2026-11-16
#   06:51:26. The lock file's mtime was 2026-11-18 00:08, so `exec 9>"$LOCK"`
#   HAD run that tick; every path below the lock block calls log(); therefore
#   the guard was exiting at the old `flock -n 9 || exit 0` — SILENTLY, for two
#   days, with nothing anywhere saying the watchdog had stood down.
#   DirCoMedia's project law says a guard must be "tested against a DEAD
#   target". The old guard's failure BRANCH had never been tested at all
#   (M7FARQP). This harness tests exactly that branch.
#
# HERMETIC: runs the REAL shipped script with its paths redirected into a temp
# dir and pm2/curl/pgrep replaced by recording stubs on PATH. It never reads or
# writes the live log/lock/state, never calls the real pm2, and never touches
# the live stack (KAXN8NP).
#
# Negative controls (each reverts ONE change; each must go RED):
#   --control-silent      restore the original 2 silent lock lines
#   --control-noinherit   drop `9>&-` from the pm2 spawns
#   --control-nostale     never break a stale lock
#   --control-nothrottle  make nag() an unconditional log()
# ═══════════════════════════════════════════════════════════════════════════
set -uo pipefail

GUARD_SRC="$(cd "$(dirname "$0")" && pwd)/dircomedia-guard.sh"
[ -f "$GUARD_SRC" ] || { echo "FATAL: $GUARD_SRC missing"; exit 1; }

CTL_SILENT=0; CTL_NOINHERIT=0; CTL_NOSTALE=0; CTL_NOTHROTTLE=0
for a in "$@"; do case "$a" in
  --control-silent) CTL_SILENT=1 ;;
  --control-noinherit) CTL_NOINHERIT=1 ;;
  --control-nostale) CTL_NOSTALE=1 ;;
  --control-nothrottle) CTL_NOTHROTTLE=1 ;;
  *) echo "unknown arg: $a"; exit 2 ;;
esac; done

PASS=0; FAIL=0; FAILED_LINES=()
ok()  { PASS=$((PASS+1)); printf '  ok   %s\n' "$1"; }
bad() { FAIL=$((FAIL+1)); FAILED_LINES+=("$1"); printf '  FAIL %s\n' "$1"; }
is()  { if [ "$2" = "1" ]; then ok "$1"; else bad "$1${3:+ -- $3}"; fi }

T=$(mktemp -d /tmp/mwnmnt9-guard.XXXXXX) || exit 1
cleanup() { [ -n "${HOLDER_PID:-}" ] && kill "$HOLDER_PID" 2>/dev/null; rm -rf "$T"; }
trap cleanup EXIT

BIN="$T/bin"; mkdir -p "$BIN"
LOG="$T/guard.log"; STATE="$T/guard.state"; LOCK="$T/guard.lock"; ECO="$T/ecosystem.config.js"
FD9="$T/child-fd9.txt"; PM2CALLS="$T/pm2-calls.txt"
echo 'module.exports={apps:[]}' > "$ECO"

# ── stubs: nothing here can reach the live stack ──────────────────────────
cat > "$BIN/pm2" <<STUB
#!/usr/bin/env bash
echo "pm2 \$*" >> "$PM2CALLS"
# Does this child still hold the guard's lock fd? THE inheritance probe.
if [ -e /proc/self/fd/9 ]; then echo "FD9_OPEN \$1" >> "$FD9"; else echo "FD9_CLOSED \$1" >> "$FD9"; fi
case "\$1" in
  ping)  [ "\$(cat "$T/pm2_up" 2>/dev/null)" = "0" ] && exit 1; echo pong; exit 0 ;;
  jlist) cat "$T/jlist.json" 2>/dev/null || echo '[]'; exit 0 ;;
  *)     exit 0 ;;
esac
STUB
cat > "$BIN/pgrep" <<STUB
#!/usr/bin/env bash
[ "\$(cat "$T/pm2_up" 2>/dev/null)" = "0" ] && exit 1
exit 0
STUB
cat > "$BIN/curl" <<STUB
#!/usr/bin/env bash
printf '%s' "\$(cat "$T/http_code" 2>/dev/null || echo 000)"
exit 0
STUB
# pm2-safe-save lives at an absolute path inside the guard; shadow the dir.
mkdir -p "$T/fake-vintinuum-api/scripts"
printf '#!/usr/bin/env bash\nexit 0\n' > "$T/fake-vintinuum-api/scripts/pm2-safe-save.sh"
chmod +x "$T/fake-vintinuum-api/scripts/pm2-safe-save.sh" "$BIN"/*

# ── build the subject: the REAL script, paths redirected ──────────────────
SUBJ="$T/guard-under-test.sh"
python3 -I - "$GUARD_SRC" "$SUBJ" "$LOG" "$STATE" "$LOCK" "$ECO" "$T" \
  "$CTL_SILENT" "$CTL_NOINHERIT" "$CTL_NOSTALE" "$CTL_NOTHROTTLE" <<'PY'
import sys, re
src_p, out_p, log, state, lock, eco, tmp = sys.argv[1:8]
c_silent, c_noinherit, c_nostale, c_nothrottle = (x == "1" for x in sys.argv[8:12])
s = open(src_p, encoding="utf-8").read()
def sub1(old, new, why):
    if s.count(old) != 1:
        sys.exit("ABORT: anchor drifted (%s): %r" % (why, old[:60]))
    return s.replace(old, new)
s = sub1('LOG="/home/vinta/.dircomedia-guard.log"', 'LOG="%s"' % log, "LOG")
s = sub1('STATE="/home/vinta/.dircomedia-guard.state"', 'STATE="%s"' % state, "STATE")
s = sub1('LOCK="/home/vinta/.dircomedia-guard.lock"', 'LOCK="%s"' % lock, "LOCK")
s = sub1('ECOSYSTEM="/home/vinta/dircomedia/ecosystem.config.js"', 'ECOSYSTEM="%s"' % eco, "ECOSYSTEM")
s = sub1('/home/vinta/vintinuum-api/scripts/pm2-safe-save.sh',
         '%s/fake-vintinuum-api/scripts/pm2-safe-save.sh' % tmp, "safe-save")
# keep the harness fast: the shipped verify loop sleeps 15x4s
s = sub1('for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do\n    sleep 4',
         'for i in 1 2; do\n    sleep 0', "verify loop")
# ── negative controls: each reverts exactly ONE shipped change ──
if c_silent:
    m = re.search(r'^# == Single-instance.*?^rm -f "\$BUSY_STAMP" 2>/dev/null \|\| true\n',
                  s, re.S | re.M)
    if not m: sys.exit("ABORT: --control-silent anchor drifted; tally is NOT evidence")
    s = s[:m.start()] + 'exec 9>"$LOCK" || exit 0\nflock -n 9 || exit 0\n' + s[m.end():]
if c_noinherit:
    n = s.count(" 9>&-")
    if n < 1: sys.exit("ABORT: --control-noinherit found no `9>&-`; tally is NOT evidence")
    s = s.replace(" 9>&-", "")
if c_nostale:
    if s.count("STALE_LOCK_SECS=900") != 1: sys.exit("ABORT: --control-nostale anchor drifted")
    s = s.replace("STALE_LOCK_SECS=900", "STALE_LOCK_SECS=99999999")
if c_nothrottle:
    if s.count('    age=$(_age "$NAG_STAMP")') != 1: sys.exit("ABORT: --control-nothrottle anchor drifted")
    s = re.sub(r'nag\(\) \{.*?\n\}\n', 'nag() { log "$*"; }\n', s, count=1, flags=re.S)
open(out_p, "w", encoding="utf-8").write(s)
PY
rc=$?; [ $rc -ne 0 ] && { echo "HARNESS ABORT (control failed to apply) rc=$rc"; exit 1; }
chmod +x "$SUBJ"
bash -n "$SUBJ" || { echo "HARNESS ABORT: subject does not parse"; exit 1; }

run_guard() { ( PATH="$BIN:$PATH" HOME="$T" bash "$SUBJ" >/dev/null 2>&1; echo $? ); }
newlines() { local n="$1"; tail -n +"$((n+1))" "$LOG" 2>/dev/null; }
loglen()   { wc -l < "$LOG" 2>/dev/null || echo 0; }

echo "== MWNMNT9 guard-lock verifier =="
echo "subject: $GUARD_SRC"
echo "controls: silent=$CTL_SILENT noinherit=$CTL_NOINHERIT nostale=$CTL_NOSTALE nothrottle=$CTL_NOTHROTTLE"

# vacuity guard: the subject must really be the shipped guard
is "V1 subject carries the guard's own banner" \
   "$([ "$(grep -c 'dircomedia stack from ecosystem.config.js' "$SUBJ")" -ge 1 ] && echo 1 || echo 0)"
is "V2 subject's paths are ALL redirected into the temp dir (no live path survives)" \
   "$([ "$(grep -c '/home/vinta/\.dircomedia-guard\|/home/vinta/dircomedia/ecosystem' "$SUBJ")" -eq 0 ] && echo 1 || echo 0)" \
   "a live path survived the rewrite"

# ─────────────────────────────────────────────────────────────────────────
echo "-- A: the reported bug: a BUSY lock must not be silent --"
echo 1 > "$T/pm2_up"; echo 000 > "$T/http_code"; echo '[]' > "$T/jlist.json"
: > "$LOG"
# a REAL long-lived holder of a REAL flock on the lock file
( exec 9>"$LOCK"; flock 9; sleep 120 ) & HOLDER_PID=$!
sleep 0.7
is "A0 the holder really holds it (control: flock -n must fail)" \
   "$( (exec 8>"$LOCK"; flock -n 8) 2>/dev/null && echo 0 || echo 1 )" \
   "the fixture never acquired the lock, so lane A proves nothing"
L0=$(loglen); RC=$(run_guard); OUT=$(newlines "$L0")
is "A1 exits 0 on a busy lock (never wedges the cron tick)" "$([ "$RC" = "0" ] && echo 1 || echo 0)" "rc=$RC"
is "A2 LOGS that the lock was busy (the 2-day silence is gone)" \
   "$(echo "$OUT" | grep -qi 'lock busy' && echo 1 || echo 0)" \
   "no 'lock busy' line -- this is the exact 2026-11-16..18 silent-stand-down bug"
is "A3 names the lock path so an operator can act" \
   "$(echo "$OUT" | grep -qF "$LOCK" && echo 1 || echo 0)"
is "A4 says when it will break the lock" \
   "$(echo "$OUT" | grep -qi 'breaking it at' && echo 1 || echo 0)"
is "A5 did NOT touch pm2 while locked out (single-instance still holds)" \
   "$([ ! -s "$PM2CALLS" ] && echo 1 || echo 0)" "pm2 was called: $(cat "$PM2CALLS" 2>/dev/null | tr '\n' ';')"

echo "-- B: the refusal is THROTTLED, never muted (log hit 804,616 bytes) --"
L1=$(loglen); run_guard >/dev/null; OUT2=$(newlines "$L1")
is "B1 a second tick inside NAG_SECS adds no new 'lock busy' line" \
   "$([ "$(echo "$OUT2" | grep -ci 'lock busy')" -eq 0 ] && echo 1 || echo 0)" \
   "unthrottled: every 2-minute tick would write a line"
is "B2 ...and still exits 0" "$([ "$(run_guard)" = "0" ] && echo 1 || echo 0)"

echo "-- C: a STALE lock is BROKEN so the guard can never be locked out forever --"
: > "$LOG"; : > "$PM2CALLS"; : > "$FD9"
echo $(( $(date +%s) - 4000 )) > "${LOCK}.busy-since"   # busy 4000s >> 900s
rm -f "${LOCK}.nagged-at"
L2=$(loglen); RC3=$(run_guard); OUT3=$(newlines "$L2")
is "C1 detects the stale lock" "$(echo "$OUT3" | grep -qi 'STALE LOCK' && echo 1 || echo 0)" \
   "a lock held longer than any real guard run was not broken -> permanent lockout"
is "C2 breaks it and says so" "$(echo "$OUT3" | grep -qi 'stale lock broken' && echo 1 || echo 0)"
is "C3 PROCEEDS to the health check after breaking (the whole point)" \
   "$(echo "$OUT3" | grep -qi 'HEALTH CHECK FAILED' && echo 1 || echo 0)" \
   "broke the lock but never ran the check"
is "C4 and actually tried to restore the dead stack" \
   "$(echo "$OUT3" | grep -qi 'restoring dircomedia stack' && echo 1 || echo 0)"
is "C5 the original wedged holder is still alive (we orphaned its inode, not killed it)" \
   "$(kill -0 "$HOLDER_PID" 2>/dev/null && echo 1 || echo 0)"
is "C6 pm2 was reached only after the break" \
   "$([ -s "$PM2CALLS" ] && echo 1 || echo 0)"

echo "-- D: no child may inherit the lock fd (this is what created the wedge) --"
is "D0 the inheritance probe actually ran in a child" "$([ -s "$FD9" ] && echo 1 || echo 0)" \
   "no child recorded an fd-9 verdict, so lane D proves nothing"
is "D1 NO spawned pm2 child holds fd 9" \
   "$([ "$(grep -c FD9_OPEN "$FD9" 2>/dev/null)" -eq 0 ] && echo 1 || echo 0)" \
   "inherited: $(grep FD9_OPEN "$FD9" 2>/dev/null | tr '\n' ';') -- a long-lived child would hold the lock for its whole life"
is "D2 every pm2 spawn in the shipped source closes fd 9" \
   "$([ "$(grep -c 'pm2 \(start\|restart\).*9>&-' "$GUARD_SRC")" -ge 2 ] && echo 1 || echo 0)"

echo "-- E: the PM2-unresponsive refusal is throttled too --"
: > "$LOG"; rm -f "$LOCK" "${LOCK}.busy-since" "${LOCK}.nagged-at"
kill "$HOLDER_PID" 2>/dev/null; HOLDER_PID=""
echo 0 > "$T/pm2_up"
L4=$(loglen); run_guard >/dev/null; run_guard >/dev/null; run_guard >/dev/null
N=$(newlines "$L4" | grep -ci 'PM2 daemon absent')
is "E1 three ticks with pm2 down write exactly ONE refusal line (got $N)" \
   "$([ "$N" -eq 1 ] && echo 1 || echo 0)" \
   "2787 such lines had grown the live log to 804,616 bytes"
is "E2 the refusal is still PRESENT (throttled, not muted)" "$([ "$N" -ge 1 ] && echo 1 || echo 0)"

echo "-- F: the healthy path is unchanged: free lock + all green = silent --"
: > "$LOG"; rm -f "$LOCK" "${LOCK}.busy-since" "${LOCK}.nagged-at"
echo 1 > "$T/pm2_up"; echo 200 > "$T/http_code"
python3 -I -c '
import json,sys
names="dircomedia-api dircomedia-frontend dircomedia-gateway dircomedia-shim dircomedia-beat dircomedia-worker dircomedia-tunnel".split()
json.dump([{"name":n,"pm2_env":{"status":"online"}} for n in names], open(sys.argv[1],"w"))
' "$T/jlist.json"
L5=$(loglen); RC5=$(run_guard)
is "F1 healthy run exits 0" "$([ "$RC5" = "0" ] && echo 1 || echo 0)" "rc=$RC5"
is "F2 healthy run logs nothing (no new noise)" \
   "$([ "$(newlines "$L5" | grep -c .)" -eq 0 ] && echo 1 || echo 0)" \
   "logged: $(newlines "$L5" | tr '\n' ';')"
is "F3 healthy run records ok state" "$(grep -q '^ok ' "$STATE" && echo 1 || echo 0)"
is "F4 healthy run releases the lock (next run can take it)" \
   "$( (exec 7>"$LOCK"; flock -n 7) 2>/dev/null && echo 1 || echo 0 )"

echo
echo "$PASS/$((PASS+FAIL)) pass"
if [ "$FAIL" -gt 0 ]; then
  echo "FAILURES:"; for l in "${FAILED_LINES[@]}"; do echo "  - $l"; done
fi
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
