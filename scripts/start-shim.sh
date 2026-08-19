#!/usr/bin/env bash
# DirCoMedia owner-access shim launcher for PM2.
#
# Injects the owner secret on 127.0.0.1:4699 -> gateway :4600 so Vinta can just
# open a browser. The secret is read server-side and never reaches the browser.
#
# WHY THE WAIT LOOP: open-dashboard.sh exits non-zero if the gateway isn't
# answering yet. Under pm2 all four services start at once, so on boot the shim
# lost that race and crash-looped. We wait for the gateway instead of dying.
set -euo pipefail

for i in $(seq 1 60); do
  if curl -s -o /dev/null --max-time 3 "http://127.0.0.1:${GATEWAY_PORT:-4600}/__gateway/health"; then
    break
  fi
  echo "[shim] waiting for gateway :${GATEWAY_PORT:-4600} (${i}/60)"
  sleep 2
done

exec bash /home/vinta/dircomedia/scripts/open-dashboard.sh
