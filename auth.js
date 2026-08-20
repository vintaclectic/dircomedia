/**
 * DirCoMedia master-password gate.
 *
 * WHY THIS EXISTS (task SFM8BJE, 2026-08-20):
 * gateway.js used to demand a Cloudflare Access JWT before letting any internet
 * traffic through. Access was never attached to the hostname, so the gate had no
 * way to ever say yes — a locked door with no key cut. Every public visit got the
 * 403 "DirCoMedia is locked" page, permanently. Vinta asked for a master password
 * he can use from any device instead, so identity now comes from something he
 * knows rather than from a Zero Trust config he never finished.
 *
 * WHAT THIS DOES NOT CHANGE: the browser still never receives OWNER_API_TOKEN.
 * This module only decides WHO gets in; gateway.js still attaches the owner
 * credential server-side afterwards. That indirection is the security model and
 * is untouched.
 *
 * NO DEPENDENCIES — node builtins only. The gateway process has zero npm deps and
 * keeps it that way: this code guards accounts that post as Vinta, so its supply
 * chain is exactly as large as node itself and no larger.
 */

const crypto = require("crypto");

// scrypt cost. N=16384 keeps a login ~50-100ms on this box — slow enough that
// offline cracking of the hash is expensive, fast enough to not feel laggy.
const SCRYPT_N = 16384, SCRYPT_r = 8, SCRYPT_p = 1, KEYLEN = 32;

const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 days: "anytime anywhere"
const REISSUE_AFTER_MS = 24 * 60 * 60 * 1000;    // sliding renewal once a day
const COOKIE = "dcm_session";

// Brute-force policy. This is the only thing standing between the open internet
// and a posting surface, so it is deliberately strict.
const MAX_FAILS = 5;
const WINDOW_MS = 15 * 60 * 1000;
const FIXED_DELAY_MS = 250; // constant cost per attempt, success or failure

function hashPassword(password, saltHex) {
  const salt = saltHex ? Buffer.from(saltHex, "hex") : crypto.randomBytes(16);
  const dk = crypto.scryptSync(password, salt, KEYLEN, { N: SCRYPT_N, r: SCRYPT_r, p: SCRYPT_p });
  return `scrypt$${SCRYPT_N}$${SCRYPT_r}$${SCRYPT_p}$${salt.toString("hex")}$${dk.toString("hex")}`;
}

function verifyPassword(password, stored) {
  try {
    const parts = String(stored || "").split("$");
    if (parts.length !== 6 || parts[0] !== "scrypt") return false;
    const [, N, r, p, saltHex, hashHex] = parts;
    const dk = crypto.scryptSync(password, Buffer.from(saltHex, "hex"), KEYLEN,
      { N: parseInt(N, 10), r: parseInt(r, 10), p: parseInt(p, 10) });
    const want = Buffer.from(hashHex, "hex");
    // Length check first: timingSafeEqual throws on mismatched lengths, and a
    // thrown error would itself be an observable timing/behaviour difference.
    if (want.length !== dk.length) return false;
    return crypto.timingSafeEqual(dk, want);
  } catch { return false; }
}

// ---- sessions -------------------------------------------------------------
// A session is <expEpochMs>.<nonce>.<hmac>. Stateless by design: the gateway
// restarts often (pm2), and a restart must not log Vinta out of his phone.
function issueSession(secret, ttlMs = SESSION_TTL_MS) {
  const exp = Date.now() + ttlMs;
  const nonce = crypto.randomBytes(12).toString("hex");
  const mac = crypto.createHmac("sha256", secret).update(`${exp}.${nonce}`).digest("hex");
  return `${exp}.${nonce}.${mac}`;
}

function verifySession(token, secret) {
  if (!token || !secret) return null;
  const parts = String(token).split(".");
  if (parts.length !== 3) return null;
  const [expStr, nonce, mac] = parts;
  const exp = parseInt(expStr, 10);
  if (!Number.isFinite(exp)) return null;
  const want = crypto.createHmac("sha256", secret).update(`${expStr}.${nonce}`).digest("hex");
  const a = Buffer.from(mac), b = Buffer.from(want);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
  if (Date.now() > exp) return null; // signature valid but expired
  return { exp, nonce, stale: exp - Date.now() < SESSION_TTL_MS - REISSUE_AFTER_MS };
}

function parseCookies(header) {
  const out = {};
  for (const part of String(header || "").split(";")) {
    const i = part.indexOf("=");
    if (i > 0) out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}

/**
 * Secure must be omitted for plain-http loopback or local access breaks, but it
 * must be PRESENT for anything that arrived over the internet — otherwise the
 * session cookie could be replayed over http.
 */
function sessionCookie(token, isHttps) {
  const bits = [`${COOKIE}=${token}`, "HttpOnly", "SameSite=Strict", "Path=/",
    `Max-Age=${Math.floor(SESSION_TTL_MS / 1000)}`];
  if (isHttps) bits.push("Secure");
  return bits.join("; ");
}

function clearCookie(isHttps) {
  const bits = [`${COOKIE}=`, "HttpOnly", "SameSite=Strict", "Path=/", "Max-Age=0"];
  if (isHttps) bits.push("Secure");
  return bits.join("; ");
}

// ---- rate limiting --------------------------------------------------------
// In-memory is the right scope here: there is exactly one gateway process, and a
// restart clearing the counters is acceptable (an attacker cannot force one).
const fails = new Map(); // ip -> { count, first, until }

function rateState(ip) {
  const rec = fails.get(ip);
  if (!rec) return { locked: false, retryAfter: 0 };
  if (rec.until && Date.now() < rec.until) {
    return { locked: true, retryAfter: Math.ceil((rec.until - Date.now()) / 1000) };
  }
  return { locked: false, retryAfter: 0 };
}

function recordFail(ip) {
  const now = Date.now();
  let rec = fails.get(ip);
  if (!rec || now - rec.first > WINDOW_MS) rec = { count: 0, first: now, until: 0, strikes: rec ? rec.strikes || 0 : 0 };
  rec.count += 1;
  if (rec.count >= MAX_FAILS) {
    rec.strikes = (rec.strikes || 0) + 1;
    // Exponential backoff across repeated lockouts: 15m, 30m, 60m, ... capped 24h.
    const lock = Math.min(WINDOW_MS * Math.pow(2, rec.strikes - 1), 24 * 60 * 60 * 1000);
    rec.until = now + lock;
    rec.count = 0;
    rec.first = now;
  }
  fails.set(ip, rec);
  return rec;
}

function clearFails(ip) { fails.delete(ip); }

// Keep the map from growing without bound under a distributed attack.
setInterval(() => {
  const now = Date.now();
  for (const [ip, rec] of fails) {
    if ((!rec.until || now > rec.until) && now - rec.first > WINDOW_MS * 4) fails.delete(ip);
  }
}, 60 * 60 * 1000).unref();

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

module.exports = {
  hashPassword, verifyPassword,
  issueSession, verifySession,
  parseCookies, sessionCookie, clearCookie,
  rateState, recordFail, clearFails,
  COOKIE, FIXED_DELAY_MS, SESSION_TTL_MS, sleep,
};
