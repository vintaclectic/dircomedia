#!/usr/bin/env node
/**
 * DirCoMedia edge gateway — the single public door.
 *
 * WHY THIS EXISTS (security, 2026-08-12):
 * The Next frontend used to read NEXT_PUBLIC_OWNER_TOKEN, which Next inlines into
 * client JavaScript. That shipped the one credential authorizing posts to every one
 * of Vinta's social accounts into public chunks — anyone who loaded the page could
 * have extracted it and posted as him. CLAUDE.md law #3 ("THE ACCOUNTS ARE THE
 * ASSET") forbids exactly that. The token is now server-side only and lives here.
 *
 * THE SHAPE:
 *   internet → cloudflared tunnel → THIS (127.0.0.1:4600) → { /api/* → FastAPI :8000
 *                                                           { else   → Next     :4601
 * One public hostname means the browser calls /api/... same-origin: no CORS, and no
 * second exposed surface. The browser NEVER carries the owner token; this process
 * attaches it after the request has already proven it is allowed in.
 *
 * THE LOCKS (defense in depth):
 *   1. BIND: this process listens on 127.0.0.1 only. It is not reachable from the
 *      LAN or the internet — the sole path in is the cloudflared tunnel, which
 *      dials it from this same machine.
 *   2. CLOUDFLARE ACCESS: the real identity gate, enforced at Cloudflare's edge on
 *      dircomedia.vintaclectic.com (Google SSO, owner email only). Allowed requests
 *      arrive stamped with Cf-Access-Jwt-Assertion. Set REQUIRE_ACCESS_JWT=1 once
 *      the Access application exists and this process will refuse anything without
 *      that stamp — turning Access from a curtain into a hard requirement.
 *   3. LOCAL-CLIENT ALLOWANCE: requests genuinely arriving from this box (the
 *      tunnel, curl on localhost) are permitted so the owner can always reach the
 *      dashboard locally even if Access is mid-configuration.
 *
 * NOTE ON THE SHARED SECRET: cloudflared (2026.7.3) cannot inject a custom header
 * per ingress rule, so an X-Gateway-Secret cannot be carried by the tunnel. The
 * secret is therefore honored when present (useful for scripted/CI callers) but is
 * NOT the load-bearing lock — Access + loopback binding are. Do not reintroduce it
 * as the only gate.
 *
 * FAIL-CLOSED: if OWNER_API_TOKEN is missing, the process refuses to start rather
 * than serving an unauthenticated posting surface.
 */

const http = require("http");
const path = require("path");
const fs = require("fs");

// ---- config (env-only; nothing secret is ever written into this file) --------
function loadEnv(file) {
  try {
    for (const line of fs.readFileSync(file, "utf8").split("\n")) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)$/);
      if (m && !process.env[m[1]]) process.env[m[1]] = m[2].trim();
    }
  } catch { /* optional */ }
}
loadEnv(path.join(__dirname, "backend/.env"));
loadEnv(path.join(__dirname, ".env"));

const PORT = parseInt(process.env.GATEWAY_PORT || "4600", 10);
const NEXT_PORT = parseInt(process.env.NEXT_PORT || "4601", 10);
const API_PORT = parseInt(process.env.API_PORT || "8000", 10);
const OWNER_TOKEN = (process.env.OWNER_API_TOKEN || "").trim();
const SHARED_SECRET = (process.env.GATEWAY_SHARED_SECRET || "").trim();
const REQUIRE_ACCESS_JWT = process.env.REQUIRE_ACCESS_JWT === "1";

if (!OWNER_TOKEN) {
  console.error("[gateway] FATAL: OWNER_API_TOKEN missing — refusing to start.");
  process.exit(1);
}
if (SHARED_SECRET && SHARED_SECRET.length < 24) {
  console.error("[gateway] FATAL: GATEWAY_SHARED_SECRET set but too short — refusing to start.");
  process.exit(1);
}

// Timing-safe compare so the secret can't be recovered by measuring responses.
const crypto = require("crypto");
function safeEqual(a, b) {
  const ab = Buffer.from(String(a)), bb = Buffer.from(String(b));
  if (ab.length !== bb.length) return false;
  return crypto.timingSafeEqual(ab, bb);
}

// Endpoints that must never be reachable, even by an authenticated owner session,
// because they are machine-to-machine only.
const DENY = [/^\/api\/v1\/projects\/seed$/];

const server = http.createServer((req, res) => {
  const url = req.url || "/";

  // Liveness probe stays open so the tunnel/monitor can check health without auth.
  if (url === "/__gateway/health") {
    res.writeHead(200, { "content-type": "application/json" });
    return res.end(JSON.stringify({ status: "ok", service: "dircomedia-gateway" }));
  }

  // ---- IDENTITY GATE -------------------------------------------------------
  // A request is allowed if it proves itself one of three ways. Access is the
  // real gate for public traffic; the others keep local/owner tooling working.
  const accessJwt = req.headers["cf-access-jwt-assertion"];
  const hasSecret = SHARED_SECRET && safeEqual(req.headers["x-gateway-secret"] || "", SHARED_SECRET);
  const viaTunnel = Boolean(req.headers["cf-ray"] || req.headers["cf-connecting-ip"]);

  if (REQUIRE_ACCESS_JWT && !accessJwt && !hasSecret) {
    // Hard mode: public traffic MUST carry an Access identity. Without this flag
    // Cloudflare Access is only a curtain — anyone reaching the hostname before
    // the Access app is attached would sail through.
    res.writeHead(403, { "content-type": "text/plain" });
    return res.end("Forbidden: Cloudflare Access identity required.\n");
  }
  if (viaTunnel && !accessJwt && !hasSecret && !REQUIRE_ACCESS_JWT) {
    // Traffic arrived from the internet through Cloudflare but carries no Access
    // identity — meaning the Access application is not protecting this hostname
    // yet. Refuse rather than expose the posting surface to the open web.
    res.writeHead(403, { "content-type": "text/html" });
    return res.end(
      "<!doctype html><meta charset=utf-8><title>DirCoMedia — locked</title>" +
      "<body style=\"font:16px system-ui;background:#0b0b0f;color:#e7e7ea;padding:3rem;max-width:34rem;margin:0 auto\">" +
      "<h1 style=\"font-size:1.25rem;margin:0 0 1rem\">DirCoMedia is locked</h1>" +
      "<p style=\"line-height:1.6;color:#a9a9b3;margin:0\">This dashboard controls live social accounts, so it stays " +
      "closed until Cloudflare Access is attached to this hostname. Finish the Zero Trust setup, then reload.</p></body>"
    );
  }

  const isApi = url.startsWith("/api/");
  if (isApi && DENY.some((re) => re.test(url.split("?")[0]))) {
    res.writeHead(403, { "content-type": "application/json" });
    return res.end(JSON.stringify({ detail: "This endpoint is not exposed publicly." }));
  }

  const headers = { ...req.headers, host: `127.0.0.1:${isApi ? API_PORT : NEXT_PORT}` };
  delete headers["x-gateway-secret"]; // never forward the origin lock inward

  // The whole point: auth is attached HERE, server-side, after both locks passed.
  if (isApi) headers["authorization"] = `Bearer ${OWNER_TOKEN}`;

  const upstream = http.request(
    { host: "127.0.0.1", port: isApi ? API_PORT : NEXT_PORT, method: req.method, path: url, headers },
    (up) => {
      const h = { ...up.headers };
      // Defense-in-depth response headers (the app is owner-only; never embed it).
      h["x-frame-options"] = "DENY";
      h["x-content-type-options"] = "nosniff";
      h["referrer-policy"] = "no-referrer";
      res.writeHead(up.statusCode || 502, h);
      up.pipe(res);
    }
  );
  upstream.on("error", (e) => {
    console.error(`[gateway] upstream error (${isApi ? "api" : "next"}):`, e.message);
    if (!res.headersSent) res.writeHead(502, { "content-type": "application/json" });
    res.end(JSON.stringify({ detail: `Upstream ${isApi ? "API" : "frontend"} unavailable.` }));
  });
  req.pipe(upstream);
});

// Support websockets/HMR passthrough to Next so the dashboard stays interactive.
server.on("upgrade", (req, socket, head) => {
  const okSecret = SHARED_SECRET && safeEqual(req.headers["x-gateway-secret"] || "", SHARED_SECRET);
  const okAccess = Boolean(req.headers["cf-access-jwt-assertion"]);
  const fromInternet = Boolean(req.headers["cf-ray"] || req.headers["cf-connecting-ip"]);
  if (fromInternet && !okAccess && !okSecret) {
    socket.destroy();
    return;
  }
  const up = http.request({
    host: "127.0.0.1", port: NEXT_PORT, path: req.url,
    headers: { ...req.headers, host: `127.0.0.1:${NEXT_PORT}` },
  });
  up.on("upgrade", (upRes, upSocket, upHead) => {
    socket.write(
      `HTTP/1.1 101 Switching Protocols\r\n` +
      Object.entries(upRes.headers).map(([k, v]) => `${k}: ${v}`).join("\r\n") +
      "\r\n\r\n"
    );
    if (upHead && upHead.length) upSocket.unshift(upHead);
    upSocket.pipe(socket).pipe(upSocket);
  });
  up.on("error", () => socket.destroy());
  up.end();
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[gateway] listening 127.0.0.1:${PORT} → next :${NEXT_PORT}, api :${API_PORT}`);
  console.log(`[gateway] locks: shared-secret=ON access-jwt=${REQUIRE_ACCESS_JWT ? "REQUIRED" : "optional"}`);
});
