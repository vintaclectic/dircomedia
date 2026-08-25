/** @type {import('next').NextConfig} */
//
// ⛔ DO NOT ADD AN `env: {}` BLOCK HERE. EVER. ⛔
//
// Next's `env` block is a BUILD-TIME TEXT SUBSTITUTION, not a runtime read.
// Any `process.env.NEXT_PUBLIC_API_URL` token in app code gets literally
// replaced with whatever string the block resolves to at build time — which
// means a runtime fallback like `process.env.NEXT_PUBLIC_API_URL || ""` can
// NEVER execute its `|| ""` branch. It becomes `"<baked value>" || ""`.
//
// This previously shipped as:
//   env: { NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000" }
// ...which baked `http://localhost:8000` into every client chunk. Remote
// browsers then fetched THEIR OWN machine for the API, every request was
// refused, and the whole dashboard rendered as an empty shell (nav + chrome
// only, zero stats, zero pending approvals). Setting NEXT_PUBLIC_API_URL=""
// in .env.local does NOT save you: "" is falsy, so `|| "http://localhost:8000"`
// still fires.
//
// The correct design: SAME-ORIGIN. `lib/api.ts` uses `|| ""` so the browser
// hits https://dircomedia.com/api/*, the gateway (port 4600) verifies the
// session cookie and attaches the owner bearer token SERVER-SIDE before
// proxying to FastAPI :8000. No token ever reaches client code, no CORS,
// no second public hostname. NEXT_PUBLIC_* vars are already exposed to the
// browser by Next automatically — an `env` block buys nothing and breaks this.
//
const nextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
