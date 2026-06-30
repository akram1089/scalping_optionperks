#!/usr/bin/env bash
# List suggested ScalpDesk ports and whether they are free on this host.
set -euo pipefail

PORTS=(28790:WEB_HOST_PORT 28780:HTTP_PORT 28743:HTTPS_PORT)

echo "ScalpDesk port block (edit in .env if any are taken):"
echo ""
for entry in "${PORTS[@]}"; do
  port="${entry%%:*}"
  name="${entry##*:}"
  if ss -tln 2>/dev/null | grep -q ":${port} "; then
    status="IN USE"
  else
    status="free"
  fi
  printf "  %-16s %5s  %s\n" "${name}" "${port}" "${status}"
done
echo ""
echo "Find what uses a port:  ss -tlnp | grep 28790"
