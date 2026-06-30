# Cloudflare + ScalpDesk (scalping.optionperks.com)

## Symptom

```bash
curl -sI https://scalping.optionperks.com/api/health
# HTTP/1.1 301 Moved Permanently
# Server: cloudflare
# Location: https://scalping.optionperks.com/api/health   ← same URL = redirect loop
```

Docker is fine. **Cloudflare** (or CF + origin SSL mismatch) is causing the loop.

---

## Fix in Cloudflare dashboard

1. Open [Cloudflare](https://dash.cloudflare.com) → **optionperks.com** → **DNS**
   - `scalping` A record should point to your VPS IP
   - Note if proxy is **Proxied** (orange cloud) or **DNS only** (grey)

2. **SSL/TLS** → Overview → set encryption mode to:
   - **Full** or **Full (strict)**  
   - **NOT Flexible** ← Flexible causes HTTPS↔HTTP redirect loops with origin nginx

3. **Rules** → **Redirect Rules** / **Page Rules**
   - Remove duplicate rules for `scalping.optionperks.com` (e.g. “Always Use HTTPS” + origin also redirects)

4. Wait 1–2 minutes, then test:
   ```bash
   curl -s https://scalping.optionperks.com/api/health
   ```
   Expected: `{"status":"ok"}`

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
