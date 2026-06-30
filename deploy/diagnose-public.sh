#!/usr/bin/env bash
# Quick checks when public URL returns 301/502
set -euo pipefail

WEB_PORT="${WEB_HOST_PORT:-28790}"
DOMAIN="${DOMAIN:-scalping.optionperks.com}"

echo "=== 1. Docker web (must return JSON) ==="
curl -sS "http://127.0.0.1:${WEB_PORT}/api/health" || echo "FAIL — is web container up?"

echo ""
echo "=== 2. HTTPS redirect target ==="
curl -sSI "https://${DOMAIN}/api/health" | head -20

echo ""
echo "=== 3. nginx configs mentioning domain ==="
grep -r "${DOMAIN}" /etc/nginx/sites-enabled/ 2>/dev/null || echo "(none in sites-enabled)"

echo ""
echo "=== 4. Duplicate server_name (causes wrong vhost) ==="
grep -rn "server_name.*${DOMAIN}" /etc/nginx/ 2>/dev/null || true
