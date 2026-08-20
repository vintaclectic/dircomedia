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
      // DirCoMedia's PUBLIC DASHBOARD tunnel (a7ed37e1-...), living in the
      // Cloudflare account that owns the dircomedia.com zone (bb950374...).
      //
      // REPLACED the old 1427dc40-... tunnel on 2026-08-20 (task SFM8BJE). That
      // one was minted with ~/.cloudflared/cert.pem, which belongs to the
      // VINTACLECTIC account (a500348d...) — a different account than the zone.
      // Cloudflare refuses cross-account tunnel CNAMEs with error 1033 (HTTP
      // 530), which is precisely why api.dircomedia.com served 530 for weeks
      // while everyone hunted a DNS bug that did not exist. The DNS was right;
      // the tunnel OWNER was wrong. This tunnel was created against
      // cert-dircomedia.pem, whose token carries the zone's own accountID.
      //
      // Serves dircomedia.com + www -> gateway :4600 (master-password gated),
      // and api.dircomedia.com -> FastAPI :8000.
      name: "dircomedia-tunnel",
      script: "/home/vinta/cloudflared",
      args: "tunnel --config /home/vinta/.cloudflared/dircomedia-dashboard.yml run",
      interpreter: "none",
      cwd: "/home/vinta/dircomedia",
      autorestart: true,
      max_restarts: 20,
      combine_logs: true,
    },
  ],
};
