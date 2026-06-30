# Push ScalpDesk to GitHub

**Repository:** https://github.com/akram1089/scalping_optionperks

```powershell
cd c:\Users\tufai\OneDrive\Desktop\scalp-desk
git remote add origin https://github.com/akram1089/scalping_optionperks.git
git push -u origin main
```

## VPS deploy

On your VPS:

```bash
sudo bash deploy/vps-bootstrap.sh
git clone https://github.com/akram1089/scalping_optionperks.git /opt/scalp-desk
cd /opt/scalp-desk
cp .env.production.example .env
nano .env
bash deploy/deploy.sh --first-run
```

Point DNS **A record**: `scalping.optionperks.com` → VPS IP.
