#!/usr/bin/env node
/**
 * check-no-localhost-base.mjs — the guard that makes HB6H3YW unrepeatable.
 * (H3442HM, 2026-08-25)
 *
 * WHAT WENT WRONG: next.config.mjs carried an `env: { NEXT_PUBLIC_API_URL:
 * process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000" }` block. Next's
 * `env` is a BUILD-TIME TEXT SUBSTITUTION, so `http://localhost:8000` was
 * literally baked into every client chunk. Remote browsers then fetched THEIR
 * OWN machine for the API, every request was refused, and the dashboard
 * rendered as an empty shell for days.
 *
 * WHAT THIS DOES: after every build, scan the emitted client JavaScript for an
 * absolute localhost/127.0.0.1/0.0.0.0/[::1] origin. If one is present, the
 * build FAILS — loudly, with the offending chunk and the surrounding source —
 * so the leak can never reach production again.
 *
 * The dashboard's correct design is SAME-ORIGIN: lib/api.ts uses
 * `process.env.NEXT_PUBLIC_API_URL || ""`, the browser hits /api/* on its own
 * origin, and the gateway attaches the owner bearer token server-side.
 * Therefore NO absolute API origin belongs in client code at all.
 *
 * Run: node scripts/check-no-localhost-base.mjs   (wired to `postbuild`)
 * Env: DIRCOMEDIA_ALLOW_LOCALHOST_BUILD=1 skips the guard for a deliberate
 *      local-only build. Never set it in CI or on the server.
 */

import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const NEXT_DIR = join(ROOT, ".next");

// Directories that actually ship to the browser. Server bundles legitimately
// talk to localhost (the gateway proxies to FastAPI on :8000), so they are NOT
// scanned — only what a remote browser downloads.
const CLIENT_DIRS = [join(NEXT_DIR, "static")];

const SCAN_EXT = new Set([".js", ".mjs", ".css", ".json", ".map"]);

// An absolute local origin. Matches http(s)://localhost[:port],
// //127.0.0.1:8000, http://0.0.0.0:3000, http://[::1]:8000 — with or without
// a scheme, since a protocol-relative base leaks identically.
const LOCAL_ORIGIN =
  /(?:https?:)?\/\/(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])(?::\d+)?/gi;

function walk(dir, out = []) {
  if (!existsSync(dir)) return out;
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) walk(full, out);
    else if (SCAN_EXT.has(entry.slice(entry.lastIndexOf(".")))) out.push(full);
  }
  return out;
}

function contextAround(text, index, span = 90) {
  return text
    .slice(Math.max(0, index - span), Math.min(text.length, index + span))
    .replace(/\s+/g, " ");
}

if (process.env.DIRCOMEDIA_ALLOW_LOCALHOST_BUILD === "1") {
  console.log(
    "⚠️  check-no-localhost-base: SKIPPED (DIRCOMEDIA_ALLOW_LOCALHOST_BUILD=1). " +
      "This build is not safe to deploy remotely."
  );
  process.exit(0);
}

if (!existsSync(NEXT_DIR)) {
  console.error(
    "✗ check-no-localhost-base: no .next/ directory — run `next build` first."
  );
  process.exit(1);
}

const files = CLIENT_DIRS.flatMap((d) => walk(d));

if (files.length === 0) {
  console.error(
    "✗ check-no-localhost-base: found no client assets under .next/static — " +
      "the build looks incomplete, refusing to pass a guard that scanned nothing."
  );
  process.exit(1);
}

const hits = [];
for (const file of files) {
  const text = readFileSync(file, "utf8");
  LOCAL_ORIGIN.lastIndex = 0;
  let m;
  while ((m = LOCAL_ORIGIN.exec(text)) !== null) {
    hits.push({
      file: relative(ROOT, file),
      origin: m[0],
      context: contextAround(text, m.index),
    });
    if (hits.length > 40) break;
  }
  if (hits.length > 40) break;
}

if (hits.length > 0) {
  console.error("");
  console.error("╔══════════════════════════════════════════════════════════════╗");
  console.error("║  BUILD REJECTED — localhost API base leaked into client JS   ║");
  console.error("╚══════════════════════════════════════════════════════════════╝");
  console.error("");
  console.error(
    `Found ${hits.length} absolute local origin(s) in browser-shipped assets.`
  );
  console.error(
    "A remote browser would fetch ITS OWN machine and every request would fail,"
  );
  console.error(
    "rendering the dashboard as a silent empty shell (regression of HB6H3YW).\n"
  );
  for (const h of hits.slice(0, 10)) {
    console.error(`  ${h.file}`);
    console.error(`    origin : ${h.origin}`);
    console.error(`    context: …${h.context}…`);
    console.error("");
  }
  if (hits.length > 10) console.error(`  …and ${hits.length - 10} more.\n`);
  console.error("HOW TO FIX:");
  console.error(
    "  1. Do NOT add an `env: {}` block to next.config.mjs — it is a build-time"
  );
  console.error("     text substitution and defeats any runtime `|| \"\"` fallback.");
  console.error(
    "  2. Leave NEXT_PUBLIC_API_URL UNSET so lib/api.ts resolves to same-origin."
  );
  console.error(
    "  3. If you truly need a local-only build: DIRCOMEDIA_ALLOW_LOCALHOST_BUILD=1 npm run build"
  );
  console.error("");
  process.exit(1);
}

console.log(
  `✓ check-no-localhost-base: ${files.length} client assets clean — no absolute localhost API base shipped.`
);
