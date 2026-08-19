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
  ],
};
