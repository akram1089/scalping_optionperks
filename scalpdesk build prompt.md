# Master Build Prompt — "ScalpDesk" (Hilega Milega Scalping Platform)

> Paste this whole document into your AI code editor (Cursor / Claude Code / Windsurf)
> as the project spec. Build it milestone by milestone in the order given at the bottom.
> Replace the placeholder brand name "ScalpDesk" and the logo with **your own** — do
> not copy Lemonn's or OptionPerks' logos, trademarks, or exact page layouts. Use the
> palette and general fintech UX as inspiration only.

---

## 1. What we are building

A **personal, self-hosted intraday scalping platform** for the Zerodha Kite Connect API,
implementing the **Hilega Milega** signal strategy with full production-grade risk
management. It runs across **one or more of the operator's OWN (or immediate-family)
Zerodha accounts** — not a public multi-user SaaS. (Offering this to unrelated users
would require SEBI algo-provider empanelment and broker tie-up, which is out of scope.)

Core capabilities:
- Secure app login + linking of one or more Zerodha accounts (with optional TOTP auto-login)
- Live market data via Kite WebSocket (ticker), TradingView Lightweight Charts overlay
- Hilega Milega signal engine with multi-timeframe confirmation
- Risk guards (daily max-loss kill switch, max trades, consecutive-loss pause)
- Position sizing, bracket-order execution, partial-fill handling
- Trade management (breakeven, trailing, partial booking, time-stop, EOD square-off)
- Multi-account fan-out with isolated failure handling
- Full audit log + per-account P&L dashboard

---

## 2. Tech stack (mandatory)

| Layer        | Technology |
|--------------|-----------|
| Backend API  | **FastAPI** (Python 3.11+), Uvicorn, Pydantic v2 |
| Async/Tasks  | asyncio; APScheduler for morning login + EOD square-off; optional Celery |
| Broker SDK   | `kiteconnect` (REST) + Kite Ticker (WebSocket) |
| DB           | **PostgreSQL 16**, SQLAlchemy 2.0 (async), Alembic migrations |
| Cache/Queue  | **Redis** (live tick cache, pub/sub to frontend, rate-limit state) |
| Frontend     | **React 18 + Vite + TypeScript**, React Router, TanStack Query, Zustand |
| Charts       | **TradingView Lightweight Charts** (free, open-source) |
| Styling      | Tailwind CSS + shadcn/ui, theme tokens in section 7 |
| Realtime UI  | WebSocket (FastAPI `websockets`) → React for live ticks/positions |
| Auth         | App login: JWT (access+refresh) + bcrypt; broker creds encrypted at rest |
| Infra        | **Docker + docker-compose** (api, worker, web, postgres, redis) |
| Secrets      | `.env` + Fernet/AES encryption for broker credentials in DB |

---

## 3. High-level architecture

```
React (Vite)  ──HTTP/JWT──>  FastAPI  ──>  PostgreSQL
     │  ▲                       │
     └──WebSocket───────────────┤──> Redis (pub/sub, tick cache)
                                │
                   APScheduler worker
                   ├─ 08:45 morning Kite login (per account)
                   ├─ live signal loop (per enabled strategy)
                   └─ 15:20 EOD square-off (per account)
                                │
                        Kite REST + Kite Ticker (WebSocket)
```

The **strategy engine runs in the worker process**, not in request handlers. The API
layer is for config, auth, dashboards, and manual controls (start/stop/kill).

---

## 4. Authentication & broker linking

### 4.1 App auth
- Email + password signup/login. Hash with bcrypt. Issue JWT access (15 min) + refresh (7 d).
- All API routes except `/auth/*` require a valid JWT.

### 4.2 Zerodha account linking (per broker account)
Each Zerodha account the operator owns is stored in `broker_accounts`, with `api_key`,
`api_secret`, and (optional) `totp_secret` **encrypted** using a master key from env.

Two login modes per account:
1. **Manual (default, compliant):** operator clicks "Connect", goes through Kite's hosted
   login, callback receives `request_token`, backend exchanges it
   (`generate_session`) for the daily `access_token`.
2. **TOTP auto-login (optional):** headless flow — POST `/api/login` (user+password) →
   POST `/api/twofa` (pyotp code from stored secret) → follow redirect for
   `request_token` → exchange for `access_token`.
   ⚠️ Implement, but surface a clear warning in the UI: the exchange mandates a **manual
   login once per day** and Zerodha does not recommend automating it. Recommended default
   is one manual morning login, then auto-refresh/reuse of the token for the rest of the
   day. Store the TOTP secret encrypted; it is a full account-takeover credential.

`access_token` expires daily (~6 AM). Store it with the date; treat stale tokens as
"needs re-login". Never log tokens or secrets.

---

## 5. The Hilega Milega scalping engine

### 5.1 Indicator (compute per candle, per timeframe)
- RSI (default length 14)
- A smoothing line of RSI: WMA of RSI (default 21) — the "Hilega" line
- An EMA of RSI (default 3) — the "Milega"/fast line
- Zero/mid reference at 50
- **Long bias** when fast line crosses above the WMA line AND both are above 50
- **Short bias** when fast line crosses below the WMA line AND both are below 50
- Make all lengths/levels configurable per strategy in the DB.

### 5.2 Signal pipeline (mirror this exact decision flow)
1. **Pre-checks (gate, run every loop):** broker session healthy; daily risk guards OK
   (max loss / max trades / consecutive-loss pause / kill switch not tripped); market open
   and outside the avoid-window (skip first & last N minutes).
2. **Regime filter:** ATR within band (enough movement, not too wild); bid-ask spread ≤ cap;
   sufficient liquidity/volume; optional news/event block.
3. **Signal:** Hilega Milega trigger on entry timeframe.
4. **MTF confirmation:** higher-timeframe trend agrees.
5. **Anti-chase:** confirmation candle closed AND price not too far from signal candle.
6. **Sizing:** qty = (risk_pct × account_capital) ÷ stop_distance, rounded to lot size.
7. **Margin / open-position-limit check.**
8. **Entry:** place order (limit + slippage cap); fill-timeout → cancel/retry; handle partial.
9. **Bracket:** set initial SL + target (R:R) server-side; log entry.
10. **Manage:** book partial → SL to breakeven → trail; exits on SL hit, opposite signal,
    time-stop, or EOD square-off.
11. **Post-trade:** log, update P&L + win/loss + streak counters, re-evaluate guards.

### 5.3 Multi-account fan-out
A single signal fans out to all enabled accounts. **Size per account** (each from its own
capital). **Isolate failures** — a reject/margin-shortfall on one account must not block the
others; log it and apply the configured policy (retry, or flatten the legs that did fill).
Provide a **global kill switch** that disables every account at once.

---

## 6. Database schema (Postgres, via SQLAlchemy + Alembic)

```
users(id, email, password_hash, created_at, is_active)

broker_accounts(id, user_id FK, label, broker='zerodha',
  api_key_enc, api_secret_enc, totp_secret_enc NULL,
  zerodha_user_id, capital, auto_login bool, enabled bool,
  access_token_enc NULL, token_date, created_at)

strategies(id, user_id FK, name, instrument_type,  -- 'equity_intraday' | 'futures' | 'options'
  symbol, entry_tf, htf, params_json,              -- rsi/wma/ema lengths, levels
  risk_pct, rr_ratio, atr_band_json, spread_cap,
  avoid_open_min, avoid_close_min, max_trades_day,
  daily_max_loss, consec_loss_limit, enabled bool)

strategy_accounts(id, strategy_id FK, broker_account_id FK, enabled bool)  -- which accounts run it

signals(id, strategy_id FK, ts, side, tf, price, indicator_snapshot_json, acted bool)

orders(id, broker_account_id FK, strategy_id FK, kite_order_id, side,
  symbol, qty, price, type, status, parent_order_id NULL, ts, raw_json)

trades(id, broker_account_id FK, strategy_id FK, entry_order_id, exit_order_id,
  side, qty, entry_price, exit_price, pnl, exit_reason, opened_at, closed_at)

positions(id, broker_account_id FK, symbol, qty, avg_price, side, updated_at)

risk_events(id, broker_account_id FK NULL, strategy_id FK NULL, type, detail, ts)
  -- 'kill_switch','max_loss','consec_pause','login_fail','partial_fill', etc.

audit_log(id, user_id FK, action, target, meta_json, ts)
```

Encrypt `*_enc` columns with Fernet. Keep a 5-year retention on orders/trades/audit_log.

---

## 7. UI / Theme (match the provided screenshot)

Clean, white, modern Indian-fintech look. **Light theme primary.** Design tokens:

```
--bg:            #FFFFFF
--bg-subtle:     #F6F8FB     /* section backgrounds, cards */
--border:        #E5E9F0
--text:          #0F172A     /* near-black headings/body */
--text-muted:    #64748B
--primary:       #2D7FF9     /* primary blue buttons / links (from screenshot) */
--primary-700:   #1D5FD6     /* hover */
--primary-navy:  #14245C     /* logo dark / ticker bar bg */
--accent:        #22C55E     /* green CTAs, "ADD", positive actions */
--accent-700:    #16A34A
--up:            #16A34A     /* price up */
--down:          #EF4444     /* price down */
--warn:          #F59E0B
radius:          12px (buttons), 16px (cards)
font:            "Inter", system-ui, sans-serif
shadow:          subtle (0 1px 3px rgba(15,23,42,.08))
```

Layout & components:
- **Top live ticker bar** (navy `--primary-navy` bg) scrolling index/stock LTP with
  green/red % — like the screenshot's NIFTY/SBILIFE/INFY strip.
- **Top nav:** logo (your own), menu, primary blue "Sign In" / green "Sign Up" buttons.
- **Strategy Builder panel** echoing the screenshot's executor: Select Symbol ▾,
  Instrument Type ▾ (Equity/Futures/Options), Expiry ▾, Buy/Sell toggle, Qty ±,
  Lot Size, green **ADD/START** button.
- **Spot/Futures info row:** Spot, Volume, Max Pain, Lot Size, Day High/Low chips.
- **Dashboard:** account selector (chips, one per linked account), live P&L cards,
  open positions table, signal feed, kill-switch (big red), per-strategy on/off toggles.
- **Charts page:** TradingView Lightweight Charts with candles + overlaid Hilega Milega
  RSI sub-pane and entry/exit markers.
- Rounded buttons, generous padding, card-based sections, responsive/mobile-first.

---

## 8. Key API endpoints (FastAPI)

```
POST /auth/signup, /auth/login, /auth/refresh
GET  /accounts                         list linked broker accounts
POST /accounts                         add (encrypt creds)
POST /accounts/{id}/connect            start manual Kite login -> returns login_url
GET  /accounts/{id}/callback           receive request_token -> store access_token
POST /accounts/{id}/auto-login         trigger TOTP login (if enabled)
GET  /strategies, POST /strategies, PATCH /strategies/{id}
POST /strategies/{id}/start            enable engine
POST /strategies/{id}/stop
POST /kill-switch                      halt ALL accounts immediately
GET  /positions, GET /trades, GET /pnl?account_id=
GET  /signals?strategy_id=
WS   /ws/live                          server -> client ticks, positions, signals
```

---

## 9. Repo structure

```
scalpdesk/
├─ docker-compose.yml
├─ .env.example
├─ backend/
│  ├─ Dockerfile
│  ├─ pyproject.toml
│  ├─ app/
│  │  ├─ main.py            FastAPI app + routers + WS
│  │  ├─ config.py          settings (pydantic-settings)
│  │  ├─ db.py              async engine/session
│  │  ├─ models/            SQLAlchemy models
│  │  ├─ schemas/           pydantic
│  │  ├─ auth/              jwt, password hashing
│  │  ├─ broker/            kite client, totp login, ticker
│  │  ├─ engine/            indicators.py, pipeline.py, risk.py, sizing.py,
│  │  │                     execution.py, manage.py, fleet.py
│  │  ├─ routers/           auth, accounts, strategies, dashboard, ws
│  │  └─ scheduler.py       morning login, EOD square-off, signal loop
│  └─ alembic/
└─ frontend/
   ├─ Dockerfile
   ├─ vite.config.ts, tailwind.config.ts
   └─ src/
      ├─ theme/tokens.ts
      ├─ api/ (TanStack Query hooks)
      ├─ store/ (Zustand)
      ├─ components/ (TickerBar, StrategyBuilder, KillSwitch, PositionsTable, PnLCards)
      ├─ pages/ (Login, Dashboard, Charts, Strategies, Accounts)
      └─ charts/LightweightChart.tsx
```

---

## 10. docker-compose services

`postgres` (16, volume), `redis` (7), `api` (FastAPI/uvicorn, depends on db+redis),
`worker` (same image, runs scheduler/engine), `web` (Vite build served by nginx).
Expose api:8000, web:5173/80. All secrets via `.env`.

---

## 11. Build order (do these as sequential milestones)

1. Scaffold repo + docker-compose (postgres, redis, empty FastAPI, empty Vite). Verify boot.
2. DB models + Alembic migration + app auth (signup/login/JWT). Test with seed user.
3. Broker linking: add account, **manual** Kite login + token exchange + encrypted storage.
4. Kite Ticker WebSocket → Redis → `/ws/live` → React ticker bar (live LTP).
5. Indicators module + signal pipeline (paper mode: log signals only, no orders).
6. Risk guards + position sizing + single-account execution (bracket, fill handling).
7. Trade management (breakeven/trailing/partial/time-stop) + EOD square-off scheduler.
8. Multi-account fan-out + isolated failures + global kill switch.
9. Frontend dashboard: accounts, strategies, positions, P&L, kill switch, charts page.
10. TOTP auto-login (optional) with the daily-manual-login warning. Harden secrets.
11. Backtest/paper-trade toggle, audit log, alerts on login/guard events.

**Always start every strategy in PAPER mode and validate on ONE account before going live.**
```
