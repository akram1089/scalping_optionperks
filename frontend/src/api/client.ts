const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/** API Decimal fields arrive as JSON strings — always coerce before math/formatting. */
export function asNumber(value: unknown, fallback = 0): number {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

export interface TickData {
  symbol: string
  ltp?: number
  change_pct?: number
  volume?: number
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
}

function getToken(): string | null {
  return localStorage.getItem('access_token')
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${API_URL}${path}`, { ...options, headers })
  if (res.status === 401) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      headers['Authorization'] = `Bearer ${getToken()}`
      const retry = await fetch(`${API_URL}${path}`, { ...options, headers })
      if (!retry.ok) throw new Error(await retry.text())
      return retry.json()
    }
    localStorage.clear()
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

async function tryRefresh(): Promise<boolean> {
  const refresh = localStorage.getItem('refresh_token')
  if (!refresh) return false
  try {
    const res = await fetch(`${API_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
    if (!res.ok) return false
    const data: AuthTokens = await res.json()
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    return true
  } catch {
    return false
  }
}

export const api = {
  signup: (email: string, password: string) =>
    request<AuthTokens>('/auth/signup', { method: 'POST', body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request<AuthTokens>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: () => request<{ id: string; email: string }>('/auth/me'),

  getAccounts: () => request<BrokerAccount[]>('/accounts'),
  getAccountLimits: () => request<AccountLimits>('/accounts/limits'),
  getBrokers: () => request<BrokerMeta[]>('/accounts/brokers'),
  addAccount: (data: AddAccountPayload) =>
    request<BrokerAccount>('/accounts', { method: 'POST', body: JSON.stringify(data) }),
  connectAccount: (id: string) =>
    request<{ login_url: string }>(`/accounts/${id}/connect`, { method: 'POST' }),
  brokerLogin: (id: string) =>
    request<{ status: string; account_id: string }>(`/accounts/${id}/login`, { method: 'POST' }),
  connectEnctoken: (id: string, data: { enctoken?: string; twofa_code?: string }) =>
    request<{ status: string; user_id: string }>(`/accounts/${id}/connect-enctoken`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  loginWithTotp: (id: string) =>
    request<{ status: string; account_id: string }>(`/accounts/${id}/auto-login`, { method: 'POST' }),
  updateAccount: (id: string, data: UpdateAccountPayload) =>
    request<BrokerAccount>(`/accounts/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  bootstrapLiveTicker: () =>
    request<{ status: string }>('/accounts/live-ticker/bootstrap', { method: 'POST' }),
  getTickSnapshot: () =>
    request<{ ticks: Record<string, TickData> }>('/ticks/snapshot'),
  getAccountLiveInfo: (id: string) => request<BrokerLiveInfo>(`/accounts/${id}/live-info`),
  getChartCandles: (params: {
    instrument_token: number
    tradingsymbol: string
    exchange: string
    interval?: string
    days?: number
    account_id?: string
  }) => {
    const qs = new URLSearchParams({
      instrument_token: String(params.instrument_token),
      tradingsymbol: params.tradingsymbol,
      exchange: params.exchange,
      interval: params.interval ?? '5minute',
      days: String(params.days ?? 5),
    })
    if (params.account_id) qs.set('account_id', params.account_id)
    return request<ChartCandlesResponse>(`/charts/candles?${qs}`)
  },

  getStrategies: () => request<Strategy[]>('/strategies'),
  createStrategy: (data: CreateStrategyPayload) =>
    request<Strategy>('/strategies', { method: 'POST', body: JSON.stringify(data) }),
  startStrategy: (id: string) => request(`/strategies/${id}/start`, { method: 'POST' }),
  stopStrategy: (id: string) => request(`/strategies/${id}/stop`, { method: 'POST' }),

  getPositions: (accountId?: string) =>
    request<Position[]>(`/positions${accountId ? `?account_id=${accountId}` : ''}`),
  getTrades: (accountId?: string) =>
    request<Trade[]>(`/trades${accountId ? `?account_id=${accountId}` : ''}`),
  getPnL: (accountId?: string) =>
    request<PnL[]>(`/pnl${accountId ? `?account_id=${accountId}` : ''}`),
  getSignals: (strategyId?: string) =>
    request<Signal[]>(`/signals${strategyId ? `?strategy_id=${strategyId}` : ''}`),

  killSwitch: () => request('/kill-switch', { method: 'POST' }),
  resetKillSwitch: () => request('/kill-switch/reset', { method: 'POST' }),
  getKillSwitch: () => request<{ kill_switch: boolean }>('/kill-switch'),
  getAuditLog: () => request<AuditEntry[]>('/audit-log'),

  searchInstruments: (params: InstrumentSearchParams) => {
    const qs = new URLSearchParams()
    if (params.exchange) qs.set('exchange', params.exchange)
    if (params.segment) qs.set('segment', params.segment)
    if (params.instrument_type) qs.set('instrument_type', params.instrument_type)
    if (params.underlying) qs.set('underlying', params.underlying)
    if (params.expiry) qs.set('expiry', params.expiry)
    if (params.strike != null) qs.set('strike', String(params.strike))
    if (params.q) qs.set('q', params.q)
    if (params.limit) qs.set('limit', String(params.limit))
    return request<InstrumentMaster[]>(`/instruments?${qs}`)
  },
  getInstrumentUnderlyings: (params?: { exchange?: string; instrument_type?: string; index_only?: boolean }) => {
    const qs = new URLSearchParams()
    if (params?.exchange) qs.set('exchange', params.exchange)
    if (params?.instrument_type) qs.set('instrument_type', params.instrument_type)
    if (params?.index_only) qs.set('index_only', 'true')
    return request<{ underlying: string; count: number }[]>(`/instruments/underlyings?${qs}`)
  },
  getInstrumentExpiries: (underlying: string, instrument_type = 'CE,PE') =>
    request<string[]>(`/instruments/expiries?underlying=${encodeURIComponent(underlying)}&instrument_type=${instrument_type}`),
  getInstrumentStrikes: (underlying: string, expiry: string, option_type: 'CE' | 'PE') =>
    request<InstrumentMaster[]>(
      `/instruments/strikes?underlying=${encodeURIComponent(underlying)}&expiry=${expiry}&option_type=${option_type}`,
    ),
  getInstrumentExchanges: () => request<{ exchange: string; count: number }[]>('/instruments/exchanges'),
  getInstrumentSyncStatus: () => request<InstrumentSyncStatus | null>('/instruments/sync/status'),
  triggerInstrumentSync: () => request<InstrumentSyncResult>('/instruments/sync', { method: 'POST' }),
}

export interface BrokerAccount {
  id: string
  label: string
  broker: BrokerSlug
  auth_mode: string
  zerodha_user_id: string | null
  client_id?: string | null
  capital: number
  auto_login: boolean
  enabled: boolean
  totp_configured: boolean
  session_active: boolean
}

export type BrokerSlug = 'zerodha' | 'angel_one' | 'fyers' | 'kotak' | 'ventura'

export interface BrokerMeta {
  slug: BrokerSlug
  label: string
  auth_modes: string[]
  required_fields: Record<string, string[]>
  connect_type: string
}

export interface AccountLimits {
  max_accounts: number
  current_count: number
}

export interface AddAccountPayload {
  label: string
  broker?: BrokerSlug
  auth_mode?: string
  api_key?: string
  api_secret?: string
  zerodha_password?: string
  pin?: string
  totp_secret?: string
  zerodha_user_id?: string
  client_id?: string
  capital?: number
  auto_login?: boolean
}

export interface UpdateAccountPayload {
  label?: string
  capital?: number
  zerodha_user_id?: string
  client_id?: string
  zerodha_password?: string
  pin?: string
  totp_secret?: string
  api_key?: string
  api_secret?: string
  auto_login?: boolean
  enabled?: boolean
}

export interface ChartCandlesResponse {
  tradingsymbol: string
  exchange: string
  instrument_token: number
  interval: string
  live: boolean
  candles: { time: number; open: number; high: number; low: number; close: number; volume: number }[]
}

export interface BrokerLiveInfo {
  user_id: string | null
  user_name: string | null
  email: string | null
  broker: string | null
  exchanges: string[]
  products: string[]
  order_types: string[]
  margins: {
    net: number
    available_cash: number
    opening_balance: number
    collateral: number
    utilised_debits: number
    m2m_unrealised: number
    m2m_realised: number
  }
  holdings_count: number
  holdings_value: number
  positions: {
    open_positions: number
    day_trades: number
    unrealised_pnl: number
  }
}

export interface Strategy {
  id: string
  name: string
  instrument_type: string
  symbol: string
  entry_tf: string
  htf: string
  risk_pct: number
  rr_ratio: number
  enabled: boolean
  paper_mode: boolean
  running: boolean
  broker_account_ids: string[]
}

export interface CreateStrategyPayload {
  name: string
  symbol: string
  instrument_type?: string
  entry_tf?: string
  htf?: string
  paper_mode?: boolean
  broker_account_ids?: string[]
}

export interface Position {
  id: string
  symbol: string
  qty: number
  avg_price: number
  side: string
  stop_loss: number | null
  target: number | null
  paper: boolean
}

export interface Trade {
  id: string
  symbol: string
  side: string
  qty: number
  entry_price: number
  exit_price: number | null
  pnl: number | null
  exit_reason: string | null
  paper: boolean
}

export interface PnL {
  account_id: string
  realized_pnl: number
  unrealized_pnl: number
  total_pnl: number
  trades_today: number
  wins: number
  losses: number
}

export interface Signal {
  id: string
  strategy_id: string
  side: string
  price: number
  ts: string
  paper: boolean
  indicator_snapshot_json: Record<string, number>
}

export interface AuditEntry {
  id: string
  action: string
  target: string
  meta: Record<string, unknown>
  ts: string
}

export interface InstrumentMaster {
  instrument_token: number
  exchange: string
  tradingsymbol: string
  name: string | null
  lot_size: number
  instrument_type: string | null
  segment: string | null
  expiry: string | null
  strike: number | null
  tick_size: number | null
  is_active: boolean
}

export interface InstrumentSearchParams {
  exchange?: string
  segment?: string
  instrument_type?: string
  underlying?: string
  expiry?: string
  strike?: number
  q?: string
  limit?: number
}

export interface InstrumentSyncStatus {
  id: string
  started_at: string
  finished_at: string | null
  status: string
  source: string
  rows_upserted: number
  rows_deactivated: number
  error_detail: string | null
}

export interface InstrumentSyncResult {
  status: string
  rows_upserted: number
  rows_deactivated: number
  source: string
  sync_log_id: string
}

export function getWsUrl(): string {
  const base = import.meta.env.VITE_WS_URL || import.meta.env.VITE_API_URL?.replace('http', 'ws') || 'ws://localhost:8000'
  const token = getToken()
  return `${base}/ws/live${token ? `?token=${token}` : ''}`
}
