#!/usr/bin/env bash
# One-command deploy / redeploy on an Ubuntu server with Docker + Nginx + Certbot.
# Usage (on the server):  sudo DOMAIN=link-analysis.example.com bash deploy/deploy.sh
set -euo pipefail

DOMAIN="${DOMAIN:?Set DOMAIN, e.g. DOMAIN=link-analysis.example.com}"
PORT="${HOST_PORT:-4200}"
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SITE="/etc/nginx/sites-available/${DOMAIN}"

cd "$APP_DIR"
[ -f .env ] || { echo "Missing $APP_DIR/.env (copy .env.example and add GEMINI_API_KEY)"; exit 1; }
chmod 600 .env
grep -q '^HOST_PORT=' .env || echo "HOST_PORT=${PORT}" >> .env

echo "==> Building and starting container on 127.0.0.1:${PORT}"
HOST_PORT="$PORT" docker compose up -d --build
for _ in $(seq 1 30); do
  curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null && break
  sleep 2
done
curl -fsS "http://127.0.0.1:${PORT}/health" && echo

echo "==> Writing nginx site ${SITE}"
CF_IPS="$( { curl -fsS https://www.cloudflare.com/ips-v4; echo; curl -fsS https://www.cloudflare.com/ips-v6; } | grep -E '^[0-9a-f]' | sed 's/^/    set_real_ip_from /; s/$/;/')"
if [ ! -f "$SITE" ] || ! grep -q "managed by Certbot" "$SITE"; then
  python3 - "$APP_DIR/deploy/nginx.conf" "$SITE" "$DOMAIN" "$PORT" "$CF_IPS" <<'PY'
import sys
src, dst, domain, port, ips = sys.argv[1:]
text = open(src).read().replace("__DOMAIN__", domain).replace("__PORT__", port).replace("__CLOUDFLARE_IPS__", ips)
open(dst, "w").write(text)
PY
  ln -sf "$SITE" "/etc/nginx/sites-enabled/${DOMAIN}"
  nginx -t
  systemctl reload nginx
  echo "==> Requesting HTTPS certificate"
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect
fi

nginx -t && systemctl reload nginx
echo "==> Live at https://${DOMAIN}  (docs: https://${DOMAIN}/docs)"
