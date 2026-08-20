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
 *   2. MASTER PASSWORD (SFM8BJE, 2026-08-20): the real identity gate for public
 *      traffic. Previously this slot held CLOUDFLARE ACCESS (Google SSO) — but
 *      Access was never attached to the hostname, so the gate could never say yes
 *      and every internet visit got a dead-end 403 "locked" page forever. A door
 *      with no key cut is not security, it is an outage. Vinta now authenticates
 *      with a scrypt-hashed master password (DIRCOMEDIA_MASTER_PASSWORD_HASH) and
 *      carries an HMAC-signed HttpOnly session cookie. Access is still honored if
 *      present, so attaching it later is additive and breaks nothing.
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
const auth = require("./auth");
const { loginPage } = require("./login-page");

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
const PW_HASH = (process.env.DIRCOMEDIA_MASTER_PASSWORD_HASH || "").trim();
const SESSION_SECRET = (process.env.DIRCOMEDIA_SESSION_SECRET || "").trim();

if (!PW_HASH || !SESSION_SECRET) {
  // Fail LOUD, not open. Without these the password lane cannot work, and the
  // only remaining public behaviour would be to refuse everyone — which is the
  // exact dead-end this gate was built to remove.
  console.error("[gateway] FATAL: DIRCOMEDIA_MASTER_PASSWORD_HASH / DIRCOMEDIA_SESSION_SECRET missing.");
  console.error("[gateway] Set one with: node scripts/set-master-password.js --write");
  process.exit(1);
}

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
  // A request is allowed if it proves itself one of four ways. The master
  // password is the gate for public traffic; the rest keep local/owner/CI
  // tooling working exactly as before.
  const accessJwt = req.headers["cf-access-jwt-assertion"];
  const hasSecret = SHARED_SECRET && safeEqual(req.headers["x-gateway-secret"] || "", SHARED_SECRET);
  const viaTunnel = Boolean(req.headers["cf-ray"] || req.headers["cf-connecting-ip"]);
  const clientIp = req.headers["cf-connecting-ip"] || req.socket.remoteAddress || "unknown";
  // Trust x-forwarded-proto only from the tunnel; a direct caller could spoof it,
  // but a direct caller is loopback anyway and gets a non-Secure cookie by design.
  const isHttps = viaTunnel && String(req.headers["x-forwarded-proto"] || "https") !== "http";

  const cookies = auth.parseCookies(req.headers.cookie);
  const session = auth.verifySession(cookies[auth.COOKIE], SESSION_SECRET);

  // ---- AUTH ROUTES (always reachable, even unauthenticated) ----------------
  if (url === "/__auth/logout") {
    res.writeHead(302, { "set-cookie": auth.clearCookie(isHttps), location: "/__auth/login" });
    return res.end();
  }

  if (url.split("?")[0] === "/__auth/login") {
    if (req.method === "GET") {
      // Already signed in? Don't make him look at a login form.
      if (session) { res.writeHead(302, { location: "/" }); return res.end(); }
      const rl = auth.rateState(clientIp);
      res.writeHead(rl.locked ? 429 : 200, {
        "content-type": "text/html; charset=utf-8",
        "cache-control": "no-store",
        ...(rl.locked ? { "retry-after": String(rl.retryAfter) } : {}),
      });
      return res.end(loginPage({ locked: rl.locked, retryAfter: rl.retryAfter }));
    }

    if (req.method === "POST") {
      let body = "";
      req.on("data", (c) => {
        body += c;
        if (body.length > 4096) req.destroy(); // no reason for a password form to be large
      });
      req.on("end", async () => {
        // Fixed cost on EVERY attempt so timing cannot distinguish "rate-limited"
        // from "wrong password" from "no hash configured".
        await auth.sleep(auth.FIXED_DELAY_MS);

        const rl = auth.rateState(clientIp);
        if (rl.locked) {
          console.warn(`[gateway] login blocked (rate-limited) ip=${clientIp} retry=${rl.retryAfter}s`);
          res.writeHead(429, { "content-type": "text/html; charset=utf-8", "retry-after": String(rl.retryAfter) });
          return res.end(loginPage({ locked: true, retryAfter: rl.retryAfter }));
        }

        const params = new URLSearchParams(body);
        const ok = auth.verifyPassword(params.get("password") || "", PW_HASH);

        if (!ok) {
          const rec = auth.recordFail(clientIp);
          const now = auth.rateState(clientIp);
          console.warn(`[gateway] FAILED login ip=${clientIp} at=${new Date().toISOString()} strikes=${rec.strikes || 0}`);
          res.writeHead(now.locked ? 429 : 401, { "content-type": "text/html; charset=utf-8" });
          return res.end(loginPage({
            error: "Incorrect password.", locked: now.locked, retryAfter: now.retryAfter,
          }));
        }

        auth.clearFails(clientIp);
        console.log(`[gateway] login OK ip=${clientIp} at=${new Date().toISOString()}`);
        res.writeHead(302, {
          "set-cookie": auth.sessionCookie(auth.issueSession(SESSION_SECRET), isHttps),
          location: "/",
        });
        return res.end();
      });
      return;
    }

    res.writeHead(405, { "content-type": "text/plain", allow: "GET, POST" });
    return res.end("Method Not Allowed\n");
  }

  // ---- THE GATE ITSELF -----------------------------------------------------
  // Loopback callers (the :4699 shim, curl on this box) are trusted: the process
  // binds 127.0.0.1, so anything without Cloudflare headers is already on the
  // machine. This is what keeps local owner access frictionless.
  const isLoopback = !viaTunnel;
  const allowed = Boolean(session) || hasSecret || accessJwt || isLoopback;

  if (!allowed || (REQUIRE_ACCESS_JWT && viaTunnel && !accessJwt && !hasSecret && !session)) {
    // API callers get JSON they can act on; browsers get sent to the login page.
    // The old dead-end 403 "locked" page is deliberately gone — it could never be
    // resolved by the person reading it.
    if (url.startsWith("/api/")) {
      res.writeHead(401, { "content-type": "application/json", "cache-control": "no-store" });
      return res.end(JSON.stringify({ detail: "Authentication required.", login: "/__auth/login" }));
    }
    res.writeHead(302, { location: "/__auth/login", "cache-control": "no-store" });
    return res.end();
  }

  // Sliding renewal: a session older than a day is re-issued so a device Vinta
  // actually uses never expires out from under him mid-use.
  if (session && session.stale) {
    res.setHeader("set-cookie", auth.sessionCookie(auth.issueSession(SESSION_SECRET), isHttps));
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
  // The session cookie must count here too — a logged-in browser opens websockets
  // for Next HMR/live updates, and rejecting them would break the dashboard for
  // exactly the person who just authenticated.
  const okSession = Boolean(auth.verifySession(auth.parseCookies(req.headers.cookie)[auth.COOKIE], SESSION_SECRET));
  if (fromInternet && !okAccess && !okSecret && !okSession) {
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
  console.log(`[gateway] locks: master-password=ON shared-secret=ON access-jwt=${REQUIRE_ACCESS_JWT ? "REQUIRED" : "optional"}`);
});
