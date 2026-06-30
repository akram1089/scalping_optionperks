# Push ScalpDesk to GitHub (one-time)

Git is initialized and committed locally. GitHub CLI is installed but **you must log in** (interactive step).

## Option A — GitHub CLI (recommended)

```powershell
cd c:\Users\tufai\OneDrive\Desktop\scalp-desk

# Log in (opens browser)
gh auth login

# Create private repo and push
gh repo create scalp-desk --private --source=. --remote=origin --push --description "Self-hosted Zerodha scalping desk"
```

## Option B — Manual

1. Create a new repo at https://github.com/new named `scalp-desk` (private recommended).
2. Do **not** initialize with README (repo already exists locally).

```powershell
cd c:\Users\tufai\OneDrive\Desktop\scalp-desk
git remote add origin https://github.com/YOUR_USERNAME/scalp-desk.git
git push -u origin main
```

## VPS deploy after push

On your VPS:

```bash
sudo bash deploy/vps-bootstrap.sh
git clone https://github.com/YOUR_USERNAME/scalp-desk.git /opt/scalp-desk
cd /opt/scalp-desk
cp .env.production.example .env
nano .env
bash deploy/deploy.sh --first-run
```

Point DNS **A record**: `scalping.optionperks.com` → VPS IP.
