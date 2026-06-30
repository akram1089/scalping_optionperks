#!/usr/bin/env bash
# Install/repair host nginx vhost for scalping.optionperks.com
# Run on VPS: sudo bash deploy/install-nginx-vhost.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="${DOMAIN:-scalping.optionperks.com}"
WEB_PORT="${WEB_HOST_PORT:-28790}"
SITE="/etc/nginx/sites-available/${DOMAIN}"
ENABLED="/etc/nginx/sites-enabled/${DOMAIN}"

if [[ $EUID -ne 0 ]]; then
  echo "Run: sudo bash deploy/install-nginx-vhost.sh"
  exit 1
fi

if [[ ! -f "${ROOT}/deploy/host-nginx-scalping.conf" ]]; then
  echo "Missing ${ROOT}/deploy/host-nginx-scalping.conf — run from /opt/scalp-desk"
  exit 1
fi

# Patch WEB_HOST_PORT into config
sed "s/127.0.0.1:28790/127.0.0.1:${WEB_PORT}/g" \
  "${ROOT}/deploy/host-nginx-scalping.conf" > "/tmp/${DOMAIN}.nginx"

# If SSL certs missing, write HTTP-only version first
if [[ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
  echo "No SSL cert yet — installing HTTP-only block (run certbot after)."
  awk '/^# ── HTTP/,/^}/' "/tmp/${DOMAIN}.nginx" > "${SITE}"
else
  cp "/tmp/${DOMAIN}.nginx" "${SITE}"
fi

ln -sf "${SITE}" "${ENABLED}"

# Disable duplicate configs for same server_name (common cause of 301)
for f in /etc/nginx/sites-enabled/*; do
  [[ "$f" == "${ENABLED}" ]] && continue
  if grep -q "server_name.*${DOMAIN}" "$f" 2>/dev/null; then
    echo "Disabling duplicate: $f"
    rm -f "$f"
  fi
done

nginx -t
systemctl reload nginx

echo ""
echo "Installed ${SITE}"
echo "HTTP  test: curl -s -H 'Host: ${DOMAIN}' http://127.0.0.1/api/health"
echo "HTTPS test: curl -sk -H 'Host: ${DOMAIN}' https://127.0.0.1/api/health"
if [[ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
  echo "SSL:      certbot --nginx -d ${DOMAIN}"
fi
echo ""
echo "Cloudflare: SSL/TLS must be Full or Full (strict) — NOT Flexible"
