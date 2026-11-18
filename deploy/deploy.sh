#!/usr/bin/env bash
# One-command deploy / redeploy on an Ubuntu server with Docker + Nginx + Certbot.
# Usage (on the server):  sudo DOMAIN=link-analysis.example.com bash deploy/deploy.sh
set -euo pipefail

DOMAIN="${DOMAIN:?Set DOMAIN, e.g. DOMAIN=link-analysis.example.com}"
PORT="${HOST_PORT:-4200}"
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SITE="/etc/nginx/sites-available/${DOMAIN}"
LINK="/etc/nginx/sites-enabled/${DOMAIN}"

cd "$APP_DIR"
[ -f .env ] || { echo "Missing $APP_DIR/.env (copy .env.example and add GEMINI_API_KEY)"; exit 1; }
chmod 600 .env
grep -q '^HOST_PORT=' .env || echo "HOST_PORT=${PORT}" >> .env

echo "==> Building image (current container keeps serving)"
HOST_PORT="$PORT" docker compose build
echo "==> Swapping container on 127.0.0.1:${PORT}"
HOST_PORT="$PORT" docker compose up -d
for _ in $(seq 1 30); do
  curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "http://127.0.0.1:${PORT}/health" && echo

echo "==> Rendering nginx site ${SITE}"
CF_RANGES="$( { curl -fsS https://www.cloudflare.com/ips-v4; echo; curl -fsS https://www.cloudflare.com/ips-v6; } | grep -E '^[0-9a-f:.]+/[0-9]+$')"
[ -n "$CF_RANGES" ] || { echo "Could not fetch Cloudflare IP ranges"; exit 1; }
BACKUP=""
[ -f "$SITE" ] && BACKUP="$(mktemp)" && cp "$SITE" "$BACKUP"
python3 - "$APP_DIR/deploy/nginx.conf" "$SITE" "$DOMAIN" "$PORT" "$CF_RANGES" <<'PY'
import sys
src, dst, domain, port, ranges = sys.argv[1:]
cidrs = ranges.split()
text = (open(src).read()
        .replace("__DOMAIN__", domain).replace("__PORT__", port)
        .replace("__CLOUDFLARE_IPS__", "\n".join(f"    set_real_ip_from {c};" for c in cidrs))
        .replace("__CLOUDFLARE_GEO__", "\n".join(f"    {c} 1;" for c in cidrs)))
open(dst, "w").write(text)
PY
ln -sf "$SITE" "$LINK"

restore() {
  echo "nginx config invalid, rolling back"
  if [ -n "$BACKUP" ]; then cp "$BACKUP" "$SITE"; else rm -f "$LINK" "$SITE"; fi
  nginx -t && systemctl reload nginx
  exit 1
}

if [ -d "/etc/letsencrypt/live/${DOMAIN}" ]; then
  certbot install --nginx --cert-name "$DOMAIN" --redirect --non-interactive >/dev/null 2>&1 || restore
else
  nginx -t || restore
  systemctl reload nginx
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect || restore
fi

nginx -t || restore
systemctl reload nginx
[ -n "$BACKUP" ] && rm -f "$BACKUP"
echo "==> Live at https://${DOMAIN}  (docs: https://${DOMAIN}/docs)"
