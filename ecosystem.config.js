/**
 * DirCoMedia — PM2 process definitions.
 *
 * WHY THIS FILE EXISTS (task HG5GCNB, 2026-08-19):
 * The whole stack was found DOWN with zero `dircomedia-*` processes and no
 * ecosystem file to restore them, so every reboot silently lost the marketing
 * OS and the owner had no dashboard. Previous attempts concluded "Docker is
 * required" — that was wrong. DATABASE_URL is SQLite and the dashboard/API
 * path needs no Postgres and no Redis, so the stack runs natively.
 *
 * COMPLETED TO FIVE (task CSDK6F5, 2026-08-19): the first cut of this file
 * declared only four apps, but DEPLOY.md and docs/LIVE_DEPLOYMENT.md have
 * always named FIVE `dircomedia-*` services. The two that were missing —
 * `dircomedia-worker` (the Celery fan-out that actually performs posting) and
 * `dircomedia-tunnel` (DirCoMedia's OWN named tunnel) — were both verified
 * runnable before being declared here, not assumed. Without the worker,
 * approved posts silently never go out; without a declaration, neither
 * survives a reboot.
 *
 * Start everything:  pm2 start /home/vinta/dircomedia/ecosystem.config.js
 * Persist a reboot:  pm2 save
 *
 * NOTE ON INTERPRETERS: the Python services are launched through bash wrappers
 * in scripts/. Handing pm2 a bare `uvicorn` console-script makes it run the
 * Python shebang under Node ("SyntaxError: Invalid or unexpected token"), which
 * fails while still reporting `online` — a silent, confusing outage.
 */
module.exports = {
  apps: [
    {
      // FastAPI — the owner-token-gated API. Bound to loopback; the only public
      // path in is the gateway, which attaches auth server-side.
      name: "dircomedia-api",
      script: "/home/vinta/dircomedia/scripts/start-api.sh",
      interpreter: "bash",
      cwd: "/home/vinta/dircomedia/backend",
      autorestart: true,
      max_restarts: 20,
      combine_logs: true,
    },
    {
      // Next.js dashboard. Serves the UI only; it never sees the owner token.
      name: "dircomedia-frontend",
      script: "/home/vinta/dircomedia/scripts/start-frontend.sh",
      interpreter: "bash",
      cwd: "/home/vinta/dircomedia/frontend",
      autorestart: true,
      max_restarts: 20,
      combine_logs: true,
    },
    {
      // The single public door: /api/* -> FastAPI, everything else -> Next.
      // Fails closed if OWNER_API_TOKEN is missing.
      name: "dircomedia-gateway",
      script: "/home/vinta/dircomedia/gateway.js",
      cwd: "/home/vinta/dircomedia",
      autorestart: true,
      max_restarts: 20,
      combine_logs: true,
    },
    {
      // Owner browser access on 127.0.0.1:4699 — injects the owner secret so
      // Vinta can just open a browser with no headers and no Cloudflare setup.
      name: "dircomedia-shim",
      script: "/home/vinta/dircomedia/scripts/start-shim.sh",
      interpreter: "bash",
      cwd: "/home/vinta/dircomedia",
      autorestart: true,
      max_restarts: 20,
      combine_logs: true,
    },
    {
      // Celery fan-out — the process that PERFORMS the posting, plus the beat
      // guardians (analytics, due-schedule sweep, OAuth token refresh). Verified
      // 2026-08-19: boots to "celery@Vinta ready" with all 13 tasks registered
      // against redis://localhost:6379. Nothing posts without this running, so
      // its absence looks like "approved post never went out" rather than an
      // outage — the worst kind of silent failure.
      name: "dircomedia-worker",
      script: "/home/vinta/dircomedia/scripts/start-worker.sh",
      interpreter: "bash",
      cwd: "/home/vinta/dircomedia/backend",
      autorestart: true,
      max_restarts: 20,
      combine_logs: true,
    },
    {
      // DirCoMedia's OWN named tunnel (1427dc40-...), living in the Cloudflare
      // account that owns the dircomedia.com zone. It is NOT a duplicate of the
      // vintaclectic tunnel: that one is scoped to vintaclectic.com and can
      // never serve dircomedia.com (cross-account CNAME -> error 1033 / HTTP
      // 530). This one serves api.dircomedia.com -> 127.0.0.1:8000.
      //
      // Verified 2026-08-19: registers 4 healthy edge connections (cmh01,
      // iad08, iad21, cmh02). api.dircomedia.com still returns 530 because its
      // DNS CNAME has not been created yet — a SEPARATE, known issue. The
      // tunnel process is correct and declared; do not delete it to "fix" the
      // 530. dircomedia.vintaclectic.com does NOT depend on this process — it
      // is served by the vintinuum-named-tunnel and stays up regardless.
      name: "dircomedia-tunnel",
      script: "/home/vinta/cloudflared",
      args: "tunnel --config /home/vinta/.cloudflared/dircomedia.yml run",
      interpreter: "none",
      cwd: "/home/vinta/dircomedia",
      autorestart: true,
      max_restarts: 20,
      combine_logs: true,
    },
  ],
};
