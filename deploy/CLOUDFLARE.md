# Cloudflare + ScalpDesk (scalping.optionperks.com)

## Symptom

```bash
curl -sI https://scalping.optionperks.com/api/health
# HTTP/1.1 301 Moved Permanently
# Server: cloudflare
# Location: https://scalping.optionperks.com/api/health   ← same URL = redirect loop
```

Your diagnose output confirms:
- `127.0.0.1:28790` → OK (Docker works)
- `127.0.0.1:443` → OK (HTTPS nginx works)
- `127.0.0.1:80` → **301** (HTTP nginx redirects instead of proxying)

With **Cloudflare Flexible SSL**, Cloudflare talks to your VPS on **port 80**. Nginx returns `301 → https://...` → infinite loop.

Docker is fine. **Cloudflare + nginx :80 redirect** is the cause.

---

## Fix (pick one — or do both)

### Fix 1 — Cloudflare SSL (recommended, 1 minute)

Origin **:443 already works**. Point Cloudflare at it:

1. [Cloudflare Dashboard](https://dash.cloudflare.com) → **optionperks.com** → **SSL/TLS**
2. Set to **Full (strict)** (not Flexible)
3. Test after 1 min: `curl -s https://scalping.optionperks.com/api/health`

### Fix 2 — Repair nginx :80 on VPS

Certbot often replaces :80 with `return 301 https://...`. Reinstall our vhost:

```bash
cd /opt/scalp-desk
git pull
sudo bash deploy/install-nginx-vhost.sh
bash deploy/diagnose-public.sh
```

Port **80** must `proxy_pass http://127.0.0.1:28790` for this domain (not redirect).

---

## Verify origin (on VPS) — bypass Cloudflare

These must work **before** fixing Cloudflare:

```bash
# 1. Docker web directly
curl -s http://127.0.0.1:28790/api/health

# 2. Host nginx on HTTP (local)
curl -s -H "Host: scalping.optionperks.com" http://127.0.0.1/api/health

# 3. Host nginx on HTTPS (local, skip cert verify)
curl -sk -H "Host: scalping.optionperks.com" https://127.0.0.1/api/health
```

If (1) fails → Docker issue.  
If (1) ok but (2)/(3) fail → fix host nginx (`deploy/host-nginx-scalping.conf`).  
If (1)(2)(3) ok but public URL fails → **Cloudflare SSL mode / redirect rules**.

---

## Optional: Cloudflare real IP in nginx

If you use orange-cloud proxy, add to nginx `http` block (once per server):

```nginx
# /etc/nginx/conf.d/cloudflare-real-ip.conf
set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
set_real_ip_from 103.31.4.0/22;
set_real_ip_from 141.101.64.0/18;
set_real_ip_from 108.162.192.0/18;
set_real_ip_from 190.93.240.0/20;
set_real_ip_from 188.114.96.0/20;
set_real_ip_from 197.234.240.0/22;
set_real_ip_from 198.41.128.0/17;
set_real_ip_from 162.158.0.0/15;
set_real_ip_from 104.16.0.0/13;
set_real_ip_from 104.24.0.0/14;
set_real_ip_from 172.64.0.0/13;
set_real_ip_from 131.0.72.0/22;
real_ip_header CF-Connecting-IP;
```

Or install Cloudflare’s package: `apt install nginx-cloudflare-real-ip` (Ubuntu).

---

## Quick test: DNS only (grey cloud)

Temporarily set the `scalping` DNS record to **DNS only** (grey cloud).  
If the site works immediately → confirm Cloudflare SSL/redirect settings, then re-enable proxy with **Full (strict)**.
