#!/usr/bin/env bash
# Test origin stack bypassing Cloudflare DNS
set -euo pipefail

WEB_PORT="${WEB_HOST_PORT:-28790}"
DOMAIN="${DOMAIN:-scalping.optionperks.com}"

pass() { echo "  OK   $1"; }
fail() { echo "  FAIL $1"; }

echo "=== Origin tests (run on VPS) ==="
echo ""

if out=$(curl -sf "http://127.0.0.1:${WEB_PORT}/api/health" 2>/dev/null); then
  pass "Docker web :${WEB_PORT} -> ${out}"
else
  fail "Docker web :${WEB_PORT} — check: docker compose -f docker-compose.prod.yml ps"
fi

if out=$(curl -sf -H "Host: ${DOMAIN}" "http://127.0.0.1/api/health" 2>/dev/null); then
  pass "Host nginx :80 -> ${out}"
else
  fail "Host nginx :80 — install deploy/host-nginx-scalping.conf"
fi

if out=$(curl -sfk -H "Host: ${DOMAIN}" "https://127.0.0.1/api/health" 2>/dev/null); then
  pass "Host nginx :443 -> ${out}"
else
  fail "Host nginx :443 — SSL block or cert missing"
fi

echo ""
echo "=== Public (via Cloudflare) ==="
headers=$(curl -sI "https://${DOMAIN}/api/health" 2>/dev/null || true)
echo "$headers" | head -8
if echo "$headers" | grep -qi "server: cloudflare"; then
  echo ""
  echo "Traffic goes through Cloudflare."
  echo "If you see 301 with Location = same URL -> set SSL/TLS to Full (not Flexible)."
  echo "See: deploy/CLOUDFLARE.md"
fi
