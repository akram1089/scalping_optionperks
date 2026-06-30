#!/usr/bin/env bash
set -euo pipefail

WEB_PORT="${WEB_HOST_PORT:-28790}"
DOMAIN="${DOMAIN:-scalping.optionperks.com}"

check_json_health() {
  local url=$1
  local body
  body=$(curl -sf "$url" 2>/dev/null) || return 1
  echo "$body" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'
}

pass() { echo "  OK   $1"; }
fail() { echo "  FAIL $1"; }

echo "=== Origin tests (run on VPS) ==="
echo ""

if out=$(curl -sf "http://127.0.0.1:${WEB_PORT}/api/health" 2>/dev/null) && echo "$out" | grep -q '"status":"ok"'; then
  pass "Docker web :${WEB_PORT} -> ${out}"
else
  fail "Docker web :${WEB_PORT}"
fi

if check_json_health -H "Host: ${DOMAIN}" "http://127.0.0.1/api/health"; then
  pass "Host nginx :80 -> proxies to app (required for Cloudflare Flexible)"
else
  body=$(curl -s -H "Host: ${DOMAIN}" "http://127.0.0.1/api/health" | head -c 80)
  fail "Host nginx :80 -> ${body:-no response}"
  echo "       Fix: sudo bash deploy/install-nginx-vhost.sh"
  echo "       Port 80 must proxy_pass, NOT return 301 (causes CF loop with Flexible SSL)"
fi

if check_json_health -k -H "Host: ${DOMAIN}" "https://127.0.0.1/api/health"; then
  pass "Host nginx :443 -> {\"status\":\"ok\"}"
else
  fail "Host nginx :443 — run: sudo certbot --nginx -d ${DOMAIN}"
fi

echo ""
echo "=== Public (via Cloudflare) ==="
headers=$(curl -sI "https://${DOMAIN}/api/health" 2>/dev/null || true)
echo "$headers" | head -8
loc=$(echo "$headers" | grep -i "^location:" | tr -d '\r' || true)
if echo "$headers" | grep -qi "server: cloudflare"; then
  echo ""
  if echo "$loc" | grep -q "https://${DOMAIN}/api/health"; then
    echo "REDIRECT LOOP detected (Cloudflare + origin :80 returns 301)."
    echo "Fix 1 (recommended): Cloudflare SSL/TLS -> Full (strict)"
    echo "Fix 2: sudo bash deploy/install-nginx-vhost.sh  (proxy on :80, not redirect)"
    echo "See: deploy/CLOUDFLARE.md"
  elif curl -sf "https://${DOMAIN}/api/health" 2>/dev/null | grep -q '"status":"ok"'; then
    echo "Public URL is healthy."
  fi
fi
