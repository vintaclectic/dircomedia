#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# DirCoMedia — OPEN THE DASHBOARD, RIGHT NOW, NO CLOUDFLARE SETUP REQUIRED.
#
# WHY: dircomedia.vintaclectic.com is live and healthy, but the gateway refuses
# internet traffic that carries no owner identity (it can post to Vinta's real
# social accounts). That 403 "DirCoMedia is locked" page is the lock working,
# not a broken deploy. This script gets you IN without touching DNS at all.
#
# It starts a tiny loopback shim on 127.0.0.1:4699 that injects the owner
# secret into every request and forwards to the local gateway on :4600. You
# browse http://127.0.0.1:4699 and everything just works — no header plugin,
# no Cloudflare Access, no GoDaddy record.
#
# USAGE:  bash /home/vinta/dircomedia/scripts/open-dashboard.sh
#         then open http://127.0.0.1:4699 in any browser.
# ---------------------------------------------------------------------------
set -euo pipefail

SHIM_PORT="${SHIM_PORT:-4699}"
GATEWAY_PORT="${GATEWAY_PORT:-4600}"

if ! curl -s -o /dev/null --max-time 5 "http://127.0.0.1:${GATEWAY_PORT}/__gateway/health"; then
  echo "✗ gateway not answering on 127.0.0.1:${GATEWAY_PORT} — start it with: pm2 restart dircomedia-gateway"
  exit 1
fi

echo "✓ gateway healthy on :${GATEWAY_PORT}"
echo
echo "  OPEN THIS IN YOUR BROWSER:  http://127.0.0.1:${SHIM_PORT}"
echo "  (Ctrl-C here to stop the shim.)"
echo

SHIM_PORT="$SHIM_PORT" GATEWAY_PORT="$GATEWAY_PORT" node -e '
const http = require("http");
const fs = require("fs");

// Read the owner secret server-side only; it never reaches the browser.
let SECRET = "";
try {
  for (const line of fs.readFileSync("/home/vinta/dircomedia/backend/.env", "utf8").split("\n")) {
    const m = line.match(/^\s*GATEWAY_SHARED_SECRET\s*=\s*(.*)$/);
    if (m) SECRET = m[1].trim();
  }
} catch {}
if (!SECRET) { console.error("FATAL: GATEWAY_SHARED_SECRET not found in backend/.env"); process.exit(1); }

const SHIM = parseInt(process.env.SHIM_PORT, 10);
const GW   = parseInt(process.env.GATEWAY_PORT, 10);

http.createServer((req, res) => {
  const headers = { ...req.headers, host: `127.0.0.1:${GW}`, "x-gateway-secret": SECRET };
  const up = http.request({ host: "127.0.0.1", port: GW, path: req.url, method: req.method, headers }, (r) => {
    res.writeHead(r.statusCode || 502, r.headers);
    r.pipe(res);
  });
  up.on("error", (e) => { res.writeHead(502, {"content-type":"text/plain"}); res.end("shim upstream error: " + e.message); });
  req.pipe(up);
}).listen(SHIM, "127.0.0.1", () => {
  console.log(`[shim] 127.0.0.1:${SHIM} -> gateway :${GW} (owner secret injected)`);
});
'
