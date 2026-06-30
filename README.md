# ScalpDesk

Self-hosted intraday scalping platform for **Zerodha Kite Connect**, implementing the **Hilega Milega** signal strategy with production-grade risk management.

## Stack

- **Backend:** FastAPI, SQLAlchemy 2 (async), PostgreSQL 16, Redis 7, APScheduler
- **Frontend:** React 18, Vite, TypeScript, TanStack Query, Zustand, Tailwind CSS
- **Charts:** TradingView Lightweight Charts
- **Infra:** Docker Compose

## Quick Start

### 1. Configure environment

```bash
cp .env.example .env
```

Generate an encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set `ENCRYPTION_KEY` and `SECRET_KEY` in `.env`.

### 2. Start with Docker

```bash
docker compose up --build
```

- API: http://localhost:8000
- Web: http://localhost:5173
- API docs: http://localhost:8000/docs

### 3. Run migrations & seed (first time)

```bash
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed.py
docker compose exec api python scripts/sync_instruments.py   # first-time instrument load
```

Demo user: `demo@scalpdesk.local` / `demo12345`

### VPS Production Deploy

**Live domain:** [https://scalping.optionperks.com](https://scalping.optionperks.com)

#### DNS

Point an **A record** for `scalping.optionperks.com` to your VPS public IP.

#### Bootstrap VPS (Ubuntu, first time)

```bash
sudo bash deploy/vps-bootstrap.sh
```

#### Clone & configure

```bash
git clone https://github.com/YOUR_USER/scalp-desk.git /opt/scalp-desk
cd /opt/scalp-desk
cp .env.production.example .env
nano .env
```

Set `SECRET_KEY`, `ENCRYPTION_KEY`, `POSTGRES_PASSWORD`, and `ACME_EMAIL`. In Zerodha Kite Connect, set redirect URL to `https://scalping.optionperks.com/api/accounts/callback`.

#### Deploy

```bash
bash deploy/deploy.sh --first-run
```

Subsequent updates: `git pull && bash deploy/deploy.sh`

Migrations run automatically on API container start. Manual: `bash deploy/migrate.sh`

| Service | Role |
|---------|------|
| Caddy | HTTPS (Let's Encrypt) |
| web | React + `/api/` proxy to FastAPI |
| api | FastAPI + Alembic migrations |
| worker | Engine + scheduler |
| postgres / redis | Persistent data |

### Migration history

| Revision | Description |
|----------|-------------|
| `001` | Initial schema (users, accounts, strategies, trades, …) |
| `002` | Instrument master + sync log |
| `003` | Composite PK (exchange, tradingsymbol) for upsert |
| `004` | Enctoken auth mode + encrypted credentials |

Check current revision:

```bash
docker compose exec api alembic current
```

### Instrument master (daily 08:50 IST)

Zerodha instruments are fetched from the Kite public CSV (`https://api.kite.trade/instruments`), upserted into PostgreSQL, and stale rows are deactivated. Runs automatically at **08:50 IST** (after morning login at 08:45). Falls back to Kite Connect API if CSV is unavailable.

Manual sync:

```bash
docker compose exec api python scripts/sync_instruments.py
# or POST /instruments/sync (authenticated)
```

Query instruments: `GET /instruments?exchange=NSE&q=RELIANCE&instrument_type=EQ`

### 4. Local development (without Docker)

**Backend:**

```bash
cd backend
pip install -e .
# Start Postgres + Redis locally, set DATABASE_URL and REDIS_URL in .env
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload
python -m app.worker  # separate terminal
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

## Milestones Implemented

1. Repo scaffold + docker-compose
2. DB models + Alembic + JWT auth
3. Broker linking (manual Kite login + encrypted creds)
4. Kite Ticker → Redis → WebSocket → React ticker bar
5. Hilega Milega indicators + signal pipeline (paper mode default)
6. Risk guards + position sizing + execution
7. Trade management + EOD square-off scheduler
8. Multi-account fan-out + global kill switch
9. Frontend dashboard (accounts, strategies, positions, P&L, charts)
10. TOTP auto-login (optional, with UI warnings)
11. Paper mode toggle, audit log

## Safety

- **Always start strategies in PAPER mode** and validate on one account before live trading.
- Zerodha requires **manual login once per trading day**; TOTP auto-login is optional and not recommended.
- This is for **your own accounts only** — not a public multi-user SaaS.

## API Overview

| Endpoint | Description |
|----------|-------------|
| `POST /auth/signup`, `/auth/login` | App authentication |
| `GET/POST /accounts` | Broker account management |
| `POST /accounts/{id}/connect` | Manual Kite login |
| `GET/POST /strategies` | Strategy CRUD |
| `POST /kill-switch` | Emergency halt |
| `WS /ws/live` | Live ticks & signals |

## License

Private use only. Not financial advice.
