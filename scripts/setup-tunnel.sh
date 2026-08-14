#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# DirCoMedia — dedicated Cloudflare tunnel bootstrap  (U6PAFU2, 2026-08-14)
#
# WHY THIS SCRIPT EXISTS
# ----------------------
# api.dircomedia.com currently returns HTTP 530 / error 1033. The ingress rule
# in ~/.cloudflared/config.yml is correct; the problem is OWNERSHIP:
#
#   * the `vintinuum` tunnel (d911c951-...) lives in Cloudflare account
#     a500348dbe17f05782b1d228158da3f1, and its cert.pem is scoped to exactly
#     one zone: vintaclectic.com (a930c99ee0ef22118414f017f6b3602d).
#   * the dircomedia.com zone IS on Cloudflare (NS = mona/toby.ns.cloudflare.com)
#     but sits in a DIFFERENT account.
#   * Cloudflare refuses a cross-account tunnel CNAME with error 1033.
#
# DirHaven and DirMegle each hit this exact wall and solved it the same way:
# give the domain its OWN tunnel, in the account that owns its zone, with its
# own config and its own pm2 process. A cloudflared process is bound to exactly
# one tunnel's credentials, so accounts cannot share one daemon. This script is
# that solution for DirCoMedia.
#
# THE ONE THING THIS SCRIPT CANNOT DO FOR YOU
# -------------------------------------------
# `cloudflared tunnel login` opens a BROWSER and requires you to pick the
# dircomedia.com zone. That is an interactive, human-only step by design (it is
# what mints the account credential). Run step 1 yourself, then this script
# does everything after it.
#
# USAGE
#   bash /home/vinta/dircomedia/scripts/setup-tunnel.sh
#
# IDEMPOTENT: safe to re-run. It reuses an existing tunnel/route if present.
# ---------------------------------------------------------------------------
set -euo pipefail

CFD="/home/vinta/cloudflared"
CFDIR="/home/vinta/.cloudflared"
TUNNEL_NAME="dircomedia"
CONFIG="$CFDIR/dircomedia.yml"
ZONE="dircomedia.com"  # the apex zone the cert MUST own — see Step 1b preflight
API_HOST="api.dircomedia.com"
API_PORT=8000          # FastAPI (uvicorn app.main:app) — owner-token gated
PM2_NAME="dircomedia-tunnel"

# The apex/dashboard host is intentionally NOT routed by default. Scope A of the
# approved decision doc keeps the dashboard LOCAL; only the API goes public.
# Set ROUTE_DASHBOARD=1 to also expose the gateway (:4600) at dircomedia.com.
ROUTE_DASHBOARD="${ROUTE_DASHBOARD:-0}"
DASH_HOST="dircomedia.com"
DASH_PORT=4600         # the gateway, never Next(:4601)/FastAPI(:8000) directly

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[warn] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[FATAL] %s\033[0m\n' "$*" >&2; exit 1; }

[ -x "$CFD" ] || die "cloudflared not found at $CFD"

# --- Step 1 gate: is there an account credential for the dircomedia zone? ----
# `tunnel login` writes/overwrites $CFDIR/cert.pem. The existing cert.pem is the
# VINTACLECTIC one — clobbering it would break api.vintaclectic.com, the board,
# and every other route on the main tunnel. So we make the user stash it.
say "Step 1/6 — checking for a dircomedia-scoped Cloudflare credential"
if [ ! -f "$CFDIR/cert-dircomedia.pem" ]; then
  cat <<EOF

  No $CFDIR/cert-dircomedia.pem found. Do this ONCE, by hand:

    # 1. protect the existing vintaclectic cert (DO NOT SKIP — login overwrites it)
    cp $CFDIR/cert.pem $CFDIR/cert-vintaclectic.pem

    # 2. log in and SELECT THE dircomedia.com ZONE in the browser
    $CFD tunnel login

    # 3. save the freshly-minted cert under the dircomedia name
    cp $CFDIR/cert.pem $CFDIR/cert-dircomedia.pem

    # 4. restore vintaclectic as the default cert (keeps the main tunnel sane)
    cp $CFDIR/cert-vintaclectic.pem $CFDIR/cert.pem

    # 5. re-run this script
    bash $0

EOF
  die "interactive login required (browser step — cannot be automated)"
fi

export TUNNEL_ORIGIN_CERT="$CFDIR/cert-dircomedia.pem"
say "Using credential: $TUNNEL_ORIGIN_CERT"

# --- Step 1b: PROVE the cert owns dircomedia.com ----------------------------
# Added 2026-08-14 after this script silently built the whole stack in the WRONG
# Cloudflare account. The mere EXISTENCE of cert-dircomedia.pem proves nothing:
# `cloudflared tunnel login` reuses whatever account the browser was already
# signed into, and if that was Bjustice@gmail.com it hands back another
# vintaclectic cert with no warning. That produced tunnel 1427dc40 — healthy, 4
# edge connections, and permanently unable to serve dircomedia.com (error 1033).
# The tell was `route dns` rewriting the hostname as
# "api.dircomedia.com.vintaclectic.com" — the cert's default zone leaking in.
# So: ask Cloudflare which zones this token can actually see, and refuse to
# build anything until dircomedia.com is one of them.
say "Step 1b/6 — verifying the cert actually owns $ZONE"
_cert_b64="$(sed -e '1d' -e '$d' "$CFDIR/cert-dircomedia.pem" | tr -d '\n')"
_cf_token="$(printf '%s' "$_cert_b64" | base64 -d 2>/dev/null \
  | python3 -c 'import sys,json; print(json.load(sys.stdin).get("apiToken",""))' 2>/dev/null || true)"

if [ -z "$_cf_token" ]; then
  warn "could not decode an apiToken from cert-dircomedia.pem — skipping preflight"
else
  _zones="$(curl -sf -H "Authorization: Bearer $_cf_token" \
    "https://api.cloudflare.com/client/v4/zones?per_page=50" 2>/dev/null \
    | python3 -c 'import sys,json; print(" ".join(z["name"] for z in json.load(sys.stdin).get("result",[])))' 2>/dev/null || true)"
  say "  zones visible to this cert: ${_zones:-<none>}"

  case " $_zones " in
    *" $ZONE "*)
      say "  ✅ $ZONE is in scope — safe to proceed" ;;
    *)
      cat >&2 <<EOF

  ❌ WRONG CLOUDFLARE ACCOUNT — refusing to build (this is the attempt-#3 trap).

  cert-dircomedia.pem can see: ${_zones:-<no zones>}
  but it CANNOT see:           $ZONE

  Creating a tunnel now would "succeed", come up healthy, and still serve
  HTTP 530 / error 1033 forever, because Cloudflare refuses cross-account
  tunnel CNAMEs. That already happened once (tunnel 1427dc40).

  FIX — the browser account is the whole problem:
    1. rm $CFDIR/cert-dircomedia.pem
    2. Sign OUT of Cloudflare in your browser (or use a private window),
       then sign in with the account that owns $ZONE.
    3. TUNNEL_ORIGIN_CERT=$CFDIR/cert-dircomedia.pem $CFD tunnel login
       -> the zone picker MUST list $ZONE. If it does not, you are still in
          the wrong account. Stop and switch accounts.
    4. Re-run this script; this check will pass.

  NOTE: DirCoMedia is ALREADY LIVE at https://dircomedia.vintaclectic.com —
  this vanity domain is optional. See DEPLOY.md §0.

EOF
      die "cert does not own $ZONE (see above)" ;;
  esac
fi

# --- Step 2: create the tunnel (idempotent) ---------------------------------
say "Step 2/6 — ensuring tunnel '$TUNNEL_NAME' exists"
if "$CFD" tunnel list 2>/dev/null | awk '{print $2}' | grep -qx "$TUNNEL_NAME"; then
  warn "tunnel '$TUNNEL_NAME' already exists — reusing"
else
  "$CFD" tunnel create "$TUNNEL_NAME"
fi

TUNNEL_ID="$("$CFD" tunnel list 2>/dev/null | awk -v n="$TUNNEL_NAME" '$2==n {print $1}' | head -1)"
[ -n "$TUNNEL_ID" ] || die "could not resolve tunnel id for '$TUNNEL_NAME'"
say "Tunnel ID: $TUNNEL_ID"

CREDS="$CFDIR/$TUNNEL_ID.json"
[ -f "$CREDS" ] || die "credentials file missing: $CREDS"

# --- Step 3: write the dedicated config -------------------------------------
# http2 (not the `auto`/QUIC default) for the same reason every other config in
# this directory forces it: cloudflared's QUIC path drops WebSocket Upgrade
# headers in transit, which breaks live features while health checks stay green.
say "Step 3/6 — writing $CONFIG"
{
  cat <<EOF
# DirCoMedia's OWN named tunnel — generated by scripts/setup-tunnel.sh
# Lives in the Cloudflare account that owns the dircomedia.com zone. That
# co-location is the entire point: the vintaclectic tunnel (d911c951-...)
# could never serve dircomedia.com because Cloudflare refuses cross-account
# tunnel CNAMEs with error 1033 — which is exactly the 530 that
# api.dircomedia.com served before this tunnel existed. The DNS was right; the
# tunnel OWNER was wrong.
tunnel: $TUNNEL_ID
credentials-file: $CREDS

protocol: http2

originRequest:
  disableChunkedEncoding: false
  noHappyEyeballs: true
  connectTimeout: 30s
  tlsTimeout: 10s
  tcpKeepAlive: 30s
  keepAliveTimeout: 1h30m
  keepAliveConnections: 100

ingress:
  # The FastAPI backend. Owner-token gated at the app layer (OWNER_API_TOKEN),
  # so exposing it is safe; approve-first still governs every public post.
  - hostname: $API_HOST
    service: http://127.0.0.1:$API_PORT
    originRequest:
      disableChunkedEncoding: false
      keepAliveTimeout: 1h30m
EOF

  if [ "$ROUTE_DASHBOARD" = "1" ]; then
    cat <<EOF
  # Dashboard — points at the GATEWAY (:4600), never Next(:4601) or the API
  # directly. The gateway serves /api/* from FastAPI and everything else from
  # Next under ONE hostname, so the browser calls the API same-origin and never
  # receives the OWNER_API_TOKEN.
  - hostname: $DASH_HOST
    service: http://127.0.0.1:$DASH_PORT
    originRequest:
      disableChunkedEncoding: false
      keepAliveTimeout: 1h30m
EOF
  else
    cat <<EOF
  # Dashboard deliberately NOT routed (Scope A of the U6PAFU2 decision doc):
  # the dashboard stays LOCAL at http://127.0.0.1:4600. To publish it later,
  # re-run with ROUTE_DASHBOARD=1 — and set up Cloudflare Access (Google SSO,
  # owner email only) on the hostname FIRST, then flip REQUIRE_ACCESS_JWT=1.
EOF
  fi

  cat <<EOF
  - service: http_status:404
EOF
} > "$CONFIG"
say "Wrote $CONFIG"

# --- Step 4: route DNS ------------------------------------------------------
say "Step 4/6 — routing DNS"
route_host() {
  local host="$1"
  if "$CFD" tunnel route dns "$TUNNEL_NAME" "$host" 2>&1 | tee /tmp/.cfroute.$$ | grep -qiE "error|failed"; then
    if grep -qi "already exists" /tmp/.cfroute.$$; then
      warn "$host already routed — if it still 530s, DELETE the old record in the"
      warn "Cloudflare dashboard (it points at the wrong account's tunnel) and re-run."
    else
      warn "route for $host reported: $(cat /tmp/.cfroute.$$)"
    fi
  else
    say "routed $host -> $TUNNEL_NAME"
  fi
  rm -f /tmp/.cfroute.$$
}
route_host "$API_HOST"
[ "$ROUTE_DASHBOARD" = "1" ] && route_host "$DASH_HOST"

# --- Step 5: pm2 service ----------------------------------------------------
say "Step 5/6 — (re)starting pm2 service '$PM2_NAME'"
pm2 delete "$PM2_NAME" >/dev/null 2>&1 || true
pm2 start "$CFD" --name "$PM2_NAME" -- tunnel --config "$CONFIG" run
pm2 save >/dev/null 2>&1 || warn "pm2 save failed — service may not survive reboot"

# --- Step 6: verify ---------------------------------------------------------
say "Step 6/6 — verifying (allowing up to 60s for edge propagation)"
sleep 8
ok=0
for i in $(seq 1 12); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$API_HOST/health" || echo 000)"
  if [ "$code" = "200" ]; then
    printf '\033[1;32m  ✓ https://%s/health -> 200\033[0m\n' "$API_HOST"; ok=1; break
  fi
  printf '  attempt %s/12: %s (waiting)\n' "$i" "$code"; sleep 5
done

if [ "$ok" != "1" ]; then
  warn "still not 200. Most likely: a STALE DNS record for $API_HOST left over from"
  warn "the old cross-account attempt. Delete it in the Cloudflare dashboard for the"
  warn "dircomedia.com zone, then re-run this script. Logs: pm2 logs $PM2_NAME"
  exit 1
fi

say "DONE — https://$API_HOST is live. See /home/vinta/dircomedia/DEPLOY.md"
