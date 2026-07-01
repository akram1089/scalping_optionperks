import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, asNumber, type BrokerAccount, type BrokerLiveInfo, type BrokerSlug, type UpdateAccountPayload } from '../api/client'
import { PageHeader, SectionCard, StatCard } from '../components/ui/PageHeader'

const BROKER_LABELS: Record<BrokerSlug, string> = {
  zerodha: 'Zerodha',
  angel_one: 'Angel One',
  fyers: 'Fyers',
  kotak: 'Kotak',
  ventura: 'Ventura',
}

type AuthMode = 'kite_connect' | 'enctoken'

const emptyForm = {
  label: '',
  broker: 'zerodha' as BrokerSlug,
  auth_mode: 'enctoken' as AuthMode,
  api_key: '',
  api_secret: '',
  zerodha_password: '',
  pin: '',
  totp_secret: '',
  zerodha_user_id: '',
  client_id: '',
  capital: 100000,
  auto_login: true,
}

function formatRupee(n: number) {
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

export function AccountsPage() {
  const qc = useQueryClient()
  const { data: accounts = [] } = useQuery({ queryKey: ['accounts'], queryFn: api.getAccounts })
  const { data: limits } = useQuery({ queryKey: ['account-limits'], queryFn: api.getAccountLimits })
  const atAccountLimit = limits ? limits.current_count >= limits.max_accounts : false
  const [showForm, setShowForm] = useState(false)
  const [enctokenModal, setEnctokenModal] = useState<string | null>(null)
  const [enctokenPaste, setEnctokenPaste] = useState('')
  const [editAccount, setEditAccount] = useState<BrokerAccount | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [liveInfo, setLiveInfo] = useState<Record<string, BrokerLiveInfo>>({})
  const [form, setForm] = useState(emptyForm)
  const [loginError, setLoginError] = useState<string | null>(null)

  const addAccount = useMutation({
    mutationFn: () =>
      api.addAccount({
        label: form.label,
        broker: form.broker,
        auth_mode: form.broker === 'zerodha' ? form.auth_mode : undefined,
        api_key: form.api_key || undefined,
        api_secret: form.api_secret || undefined,
        zerodha_password: form.zerodha_password || undefined,
        pin: form.pin || undefined,
        totp_secret: form.totp_secret || undefined,
        zerodha_user_id: form.zerodha_user_id || undefined,
        client_id: form.client_id || undefined,
        capital: form.capital,
        auto_login: form.auto_login,
      }),
    onSuccess: async (account) => {
      qc.invalidateQueries({ queryKey: ['accounts'] })
      qc.invalidateQueries({ queryKey: ['account-limits'] })
      setShowForm(false)
      setForm(emptyForm)
      const needsLogin = !account.session_active
      if (needsLogin) {
        try {
          if (account.broker === 'zerodha' && account.auth_mode === 'kite_connect') {
            const { login_url } = await api.connectAccount(account.id)
            window.open(login_url, '_blank')
          } else if (['angel_one', 'kotak', 'ventura'].includes(account.broker) && account.totp_configured) {
            await api.brokerLogin(account.id)
          } else if (account.broker === 'fyers') {
            const { login_url } = await api.connectAccount(account.id)
            window.open(login_url, '_blank')
          } else if (account.broker === 'zerodha' && account.auth_mode === 'enctoken') {
            await api.loginWithTotp(account.id)
          }
          qc.invalidateQueries({ queryKey: ['accounts'] })
        } catch (err) {
          setLoginError((err as Error).message)
        }
      }
    },
    onError: (err: Error) => setLoginError(err.message),
  })

  const connect = useMutation({
    mutationFn: (id: string) => api.connectAccount(id),
    onSuccess: (data) => window.open(data.login_url, '_blank'),
  })

  const loginWithTotp = useMutation({
    mutationFn: (id: string) => api.loginWithTotp(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ['accounts'] })
      setLoginError(null)
      setEnctokenModal(null)
      setEnctokenPaste('')
      fetchLiveInfo.mutate(id)
    },
    onError: (err: Error) => setLoginError(err.message),
  })

  const connectEnctokenPaste = useMutation({
    mutationFn: ({ id, enctoken }: { id: string; enctoken: string }) =>
      api.connectEnctoken(id, { enctoken }),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ['accounts'] })
      setEnctokenModal(null)
      setEnctokenPaste('')
      setLoginError(null)
      fetchLiveInfo.mutate(id)
    },
    onError: (err: Error) => setLoginError(err.message),
  })

  const updateAccount = useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateAccountPayload }) =>
      api.updateAccount(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['accounts'] })
      setEditAccount(null)
      setLoginError(null)
    },
    onError: (err: Error) => setLoginError(err.message),
  })

  const fetchLiveInfo = useMutation({
    mutationFn: (id: string) => api.getAccountLiveInfo(id),
    onSuccess: (data, id) => {
      setLiveInfo((prev) => ({ ...prev, [id]: data }))
      setExpandedId(id)
      setLoginError(null)
    },
    onError: (err: Error) => {
      setLoginError(err.message)
      qc.invalidateQueries({ queryKey: ['accounts'] })
    },
  })

  const connected = accounts.filter((a) => a.session_active).length

  return (
    <div className="p-6 lg:p-8 max-w-[1000px]">
      <PageHeader
        title="Broker Accounts"
        subtitle={`Up to ${limits?.max_accounts ?? 5} accounts — Zerodha, Angel One, Fyers, Kotak, Ventura`}
        action={
          <button
            onClick={() => setShowForm(!showForm)}
            className="btn-primary"
            disabled={atAccountLimit && !showForm}
          >
            {showForm ? 'Cancel' : atAccountLimit ? 'Limit reached (5/5)' : '+ Add Account'}
          </button>
        }
      />

      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatCard label="Accounts" value={`${accounts.length}/${limits?.max_accounts ?? 5}`} accent="slate" />
        <StatCard label="Connected" value={connected} accent="green" />
        <StatCard label="Needs Login" value={accounts.length - connected} accent="amber" />
      </div>

      {loginError && (
        <div className="mb-4 p-3 rounded-btn bg-down/10 text-down text-sm">{loginError}</div>
      )}

      {showForm && !atAccountLimit && (
        <SectionCard
          title="Add Broker Account"
          description="Credentials are encrypted at rest. Morning auto-login runs at 08:45 IST where supported."
        >
          <form onSubmit={(e) => { e.preventDefault(); addAccount.mutate() }} className="grid sm:grid-cols-2 gap-4">
            <input placeholder="Account label" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} className="input-field" required />
            <input placeholder="Capital (₹)" type="number" value={form.capital} onChange={(e) => setForm({ ...form, capital: +e.target.value })} className="input-field" />
            <select
              value={form.broker}
              onChange={(e) => setForm({ ...form, broker: e.target.value as BrokerSlug, auth_mode: 'enctoken' })}
              className="input-field sm:col-span-2"
            >
              {(Object.keys(BROKER_LABELS) as BrokerSlug[]).map((b) => (
                <option key={b} value={b}>{BROKER_LABELS[b]}</option>
              ))}
            </select>

            {form.broker === 'zerodha' && (
              <select
                value={form.auth_mode}
                onChange={(e) => setForm({ ...form, auth_mode: e.target.value as AuthMode })}
                className="input-field sm:col-span-2"
              >
                <option value="enctoken">enctoken — TOTP auto-login</option>
                <option value="kite_connect">Kite Connect — official API</option>
              </select>
            )}

            {(form.broker === 'zerodha' || form.broker === 'kotak') && (
              <input
                placeholder={form.broker === 'kotak' ? 'Registered mobile number' : 'Zerodha User ID'}
                value={form.zerodha_user_id}
                onChange={(e) => setForm({ ...form, zerodha_user_id: e.target.value })}
                className="input-field"
              />
            )}

            {(form.broker === 'angel_one' || form.broker === 'kotak' || form.broker === 'ventura') && (
              <input
                placeholder={form.broker === 'angel_one' ? 'Client code' : 'UCC / Client ID'}
                value={form.client_id}
                onChange={(e) => setForm({ ...form, client_id: e.target.value })}
                className="input-field"
              />
            )}

            {(form.broker === 'zerodha' && form.auth_mode === 'kite_connect') || form.broker === 'fyers' || form.broker === 'ventura' ? (
              <>
                <input placeholder={form.broker === 'fyers' ? 'App ID' : 'API / App Key'} value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} className="input-field" required />
                <input placeholder="API / App Secret" type="password" value={form.api_secret} onChange={(e) => setForm({ ...form, api_secret: e.target.value })} className="input-field" required />
              </>
            ) : null}

            {form.broker === 'angel_one' && (
              <input placeholder="API Key" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} className="input-field sm:col-span-2" required />
            )}

            {form.broker === 'kotak' && (
              <input placeholder="Consumer key (from Neo Trade API)" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} className="input-field sm:col-span-2" required />
            )}

            {(form.broker === 'zerodha' && form.auth_mode === 'enctoken') || form.broker === 'kotak' ? (
              <input
                placeholder={form.broker === 'kotak' ? 'MPIN' : 'Zerodha Password'}
                type="password"
                value={form.zerodha_password}
                onChange={(e) => setForm({ ...form, zerodha_password: e.target.value })}
                className="input-field"
                required
              />
            ) : null}

            {form.broker === 'angel_one' && (
              <input placeholder="MPIN" type="password" value={form.pin} onChange={(e) => setForm({ ...form, pin: e.target.value })} className="input-field" required />
            )}

            <div className="sm:col-span-2 space-y-1">
              <input
                placeholder="TOTP Secret (base32)"
                type="password"
                value={form.totp_secret}
                onChange={(e) => setForm({ ...form, totp_secret: e.target.value })}
                className="input-field w-full"
              />
            </div>
            <label className="sm:col-span-2 flex items-start gap-2 text-sm text-text-muted">
              <input type="checkbox" className="mt-1" checked={form.auto_login} onChange={(e) => setForm({ ...form, auto_login: e.target.checked })} />
              Auto-login each morning at 08:45 IST
            </label>
            <button type="submit" disabled={addAccount.isPending} className="btn-accent sm:col-span-2">
              {addAccount.isPending ? 'Saving…' : 'Save & connect'}
            </button>
          </form>
        </SectionCard>
      )}

      {editAccount && (
        <EditAccountModal
          account={editAccount}
          onClose={() => setEditAccount(null)}
          onSave={(data) => updateAccount.mutate({ id: editAccount.id, data })}
          saving={updateAccount.isPending}
        />
      )}

      {enctokenModal && (
        <SectionCard title="Paste enctoken manually" description="F12 → Application → Cookies → kite.zerodha.com → enctoken">
          <div className="space-y-4">
            <textarea
              placeholder="Paste enctoken cookie value"
              value={enctokenPaste}
              onChange={(e) => setEnctokenPaste(e.target.value)}
              className="input-field w-full h-24 font-mono text-sm"
            />
            <div className="flex gap-3">
              <button
                onClick={() => connectEnctokenPaste.mutate({ id: enctokenModal, enctoken: enctokenPaste })}
                disabled={!enctokenPaste || connectEnctokenPaste.isPending}
                className="btn-primary"
              >
                {connectEnctokenPaste.isPending ? 'Connecting…' : 'Connect'}
              </button>
              <button onClick={() => { setEnctokenModal(null); setLoginError(null) }} className="btn-secondary">
                Cancel
              </button>
            </div>
          </div>
        </SectionCard>
      )}

      <div className="space-y-4 mt-6">
        {accounts.map((a) => (
          <AccountCard
            key={a.id}
            account={a}
            expanded={expandedId === a.id}
            liveInfo={liveInfo[a.id]}
            onToggle={() => {
              const next = expandedId === a.id ? null : a.id
              setExpandedId(next)
              if (next && a.session_active && !liveInfo[a.id]) {
                fetchLiveInfo.mutate(a.id)
              }
            }}
            onEdit={() => setEditAccount(a)}
            onReconnect={() => {
              if (a.broker === 'zerodha' && a.auth_mode === 'enctoken' && a.totp_configured) {
                loginWithTotp.mutate(a.id)
              } else if (a.broker === 'zerodha' && a.auth_mode === 'kite_connect') {
                connect.mutate(a.id)
              } else if (['angel_one', 'kotak', 'ventura'].includes(a.broker)) {
                api.brokerLogin(a.id).then(() => qc.invalidateQueries({ queryKey: ['accounts'] })).catch((e) => setLoginError(String(e)))
              } else if (a.broker === 'fyers') {
                connect.mutate(a.id)
              } else {
                setEnctokenModal(a.id)
              }
            }}
            onFetchInfo={() => fetchLiveInfo.mutate(a.id)}
            onPasteEnctoken={() => setEnctokenModal(a.id)}
            onLoginTotp={() => loginWithTotp.mutate(a.id)}
            onConnectKite={() => connect.mutate(a.id)}
            loadingReconnect={loginWithTotp.isPending}
            loadingInfo={fetchLiveInfo.isPending && fetchLiveInfo.variables === a.id}
          />
        ))}
        {accounts.length === 0 && !showForm && (
          <div className="card p-12 text-center text-text-muted">
            <p>No broker accounts linked yet.</p>
            <button onClick={() => setShowForm(true)} className="btn-primary mt-4">Add Your First Account</button>
          </div>
        )}
      </div>
    </div>
  )
}

function AccountCard({
  account: a,
  expanded,
  liveInfo,
  onToggle,
  onEdit,
  onReconnect,
  onFetchInfo,
  onPasteEnctoken,
  onLoginTotp,
  onConnectKite,
  loadingReconnect,
  loadingInfo,
}: {
  account: BrokerAccount
  expanded: boolean
  liveInfo?: BrokerLiveInfo
  onToggle: () => void
  onEdit: () => void
  onReconnect: () => void
  onFetchInfo: () => void
  onPasteEnctoken: () => void
  onLoginTotp: () => void
  onConnectKite: () => void
  loadingReconnect: boolean
  loadingInfo: boolean
}) {
  return (
    <div className="card overflow-hidden">
      <div className="p-5 flex flex-wrap items-center justify-between gap-4">
        <button type="button" onClick={onToggle} className="flex items-center gap-4 text-left flex-1 min-w-0">
          <div className={`w-10 h-10 rounded-btn flex items-center justify-center font-bold text-sm shrink-0 ${a.session_active ? 'bg-accent-50 text-accent' : 'bg-bg-subtle text-text-faint'}`}>
            {a.label.slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold">{a.label}</h3>
            <p className="text-sm text-text-muted truncate">
              <span className="font-medium">{BROKER_LABELS[a.broker] ?? a.broker}</span>
              {' · '}{formatRupee(asNumber(a.capital))} capital
              {a.zerodha_user_id ? ` · ${a.zerodha_user_id}` : ''}
              {a.client_id ? ` · ${a.client_id}` : ''}
            </p>
          </div>
        </button>
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`badge ${a.session_active ? 'bg-accent-50 text-accent' : 'bg-warn/10 text-warn'}`}>
            {a.session_active ? 'CONNECTED' : 'NEEDS LOGIN'}
          </span>
          <button type="button" onClick={onEdit} className="btn-secondary py-2 text-sm">Edit</button>
          {a.session_active ? (
            <>
              <button type="button" onClick={onFetchInfo} disabled={loadingInfo} className="btn-primary py-2 text-sm">
                {loadingInfo ? 'Loading…' : 'Refresh info'}
              </button>
              <button type="button" onClick={onReconnect} disabled={loadingReconnect} className="btn-secondary py-2 text-sm">
                {loadingReconnect ? 'Reconnecting…' : 'Reconnect'}
              </button>
            </>
          ) : (
            <>
              {a.broker === 'zerodha' && a.auth_mode === 'enctoken' && a.totp_configured && (
                <button type="button" onClick={onLoginTotp} disabled={loadingReconnect} className="btn-primary py-2 text-sm">
                  Login with TOTP
                </button>
              )}
              {a.broker === 'zerodha' && a.auth_mode === 'enctoken' && (
                <button type="button" onClick={onPasteEnctoken} className="btn-secondary py-2 text-sm">Paste enctoken</button>
              )}
              {a.broker === 'zerodha' && a.auth_mode === 'kite_connect' && (
                <button type="button" onClick={onConnectKite} className="btn-primary py-2 text-sm">Connect</button>
              )}
              {a.broker === 'fyers' && (
                <button type="button" onClick={onConnectKite} className="btn-primary py-2 text-sm">OAuth Connect</button>
              )}
              {['angel_one', 'kotak', 'ventura'].includes(a.broker) && (
                <button type="button" onClick={onLoginTotp} disabled={loadingReconnect} className="btn-primary py-2 text-sm">
                  Login
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {expanded && liveInfo && (
        <div className="px-5 pb-5 border-t border-border bg-bg-subtle/40">
          <div className="pt-4 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <InfoTile label="Net margin" value={formatRupee(liveInfo.margins.net)} highlight />
            <InfoTile label="Available cash" value={formatRupee(liveInfo.margins.available_cash)} />
            <InfoTile label="Opening balance" value={formatRupee(liveInfo.margins.opening_balance)} />
            <InfoTile label="Collateral" value={formatRupee(liveInfo.margins.collateral)} />
            <InfoTile label="Utilised" value={formatRupee(liveInfo.margins.utilised_debits)} />
            <InfoTile
              label="M2M unrealised"
              value={formatRupee(liveInfo.margins.m2m_unrealised)}
              trend={liveInfo.margins.m2m_unrealised >= 0 ? 'up' : 'down'}
            />
            <InfoTile label="Holdings" value={`${liveInfo.holdings_count} (${formatRupee(liveInfo.holdings_value)})`} />
            <InfoTile label="Open positions" value={String(liveInfo.positions.open_positions)} />
          </div>
          <div className="mt-4 flex flex-wrap gap-4 text-xs text-text-muted">
            {liveInfo.user_name && <span>Name: <strong className="text-text">{liveInfo.user_name}</strong></span>}
            {liveInfo.email && <span>Email: <strong className="text-text">{liveInfo.email}</strong></span>}
            {liveInfo.exchanges.length > 0 && <span>Exchanges: {liveInfo.exchanges.join(', ')}</span>}
            {liveInfo.products.length > 0 && <span>Products: {liveInfo.products.join(', ')}</span>}
          </div>
        </div>
      )}

      {expanded && !liveInfo && a.session_active && (
        <div className="px-5 pb-5 border-t border-border text-sm text-text-muted">
          Click <strong>Refresh info</strong> to load margins and holdings from your broker.
        </div>
      )}
    </div>
  )
}

function InfoTile({
  label,
  value,
  highlight,
  trend,
}: {
  label: string
  value: string
  highlight?: boolean
  trend?: 'up' | 'down'
}) {
  return (
    <div className={`rounded-btn border p-3 ${highlight ? 'border-accent/30 bg-accent-50/50' : 'border-border bg-surface'}`}>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-text-faint">{label}</p>
      <p className={`text-lg font-bold tabular-nums mt-0.5 ${trend === 'up' ? 'text-up' : trend === 'down' ? 'text-down' : 'text-text'}`}>
        {value}
      </p>
    </div>
  )
}

function EditAccountModal({
  account,
  onClose,
  onSave,
  saving,
}: {
  account: BrokerAccount
  onClose: () => void
  onSave: (data: UpdateAccountPayload) => void
  saving: boolean
}) {
  const [label, setLabel] = useState(account.label)
  const [capital, setCapital] = useState(asNumber(account.capital))
  const [zerodhaUserId, setZerodhaUserId] = useState(account.zerodha_user_id ?? '')
  const [password, setPassword] = useState('')
  const [totpSecret, setTotpSecret] = useState('')
  const [autoLogin, setAutoLogin] = useState(account.auto_login)
  const [enabled, setEnabled] = useState(account.enabled)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const data: UpdateAccountPayload = {
      label,
      capital,
      zerodha_user_id: zerodhaUserId || undefined,
      auto_login: autoLogin,
      enabled,
    }
    if (password) data.zerodha_password = password
    if (totpSecret) data.totp_secret = totpSecret
    onSave(data)
  }

  return (
    <SectionCard title={`Edit — ${account.label}`} description="Leave password/TOTP blank to keep existing values">
      <form onSubmit={handleSubmit} className="grid sm:grid-cols-2 gap-4">
        <input placeholder="Account label" value={label} onChange={(e) => setLabel(e.target.value)} className="input-field" required />
        <input placeholder="Capital (₹)" type="number" value={capital} onChange={(e) => setCapital(+e.target.value)} className="input-field" />
        <input placeholder="Zerodha User ID" value={zerodhaUserId} onChange={(e) => setZerodhaUserId(e.target.value)} className="input-field sm:col-span-2" />
        {account.auth_mode === 'enctoken' && (
          <input placeholder="New password (optional)" type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="input-field" />
        )}
        <input placeholder="New TOTP secret (optional)" type="password" value={totpSecret} onChange={(e) => setTotpSecret(e.target.value)} className="input-field" />
        <label className="sm:col-span-2 flex items-center gap-2 text-sm text-text-muted">
          <input type="checkbox" checked={autoLogin} onChange={(e) => setAutoLogin(e.target.checked)} />
          Morning auto-login (08:45 IST)
        </label>
        <label className="sm:col-span-2 flex items-center gap-2 text-sm text-text-muted">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          Account enabled for trading
        </label>
        <div className="sm:col-span-2 flex gap-3">
          <button type="submit" disabled={saving} className="btn-primary">
            {saving ? 'Saving…' : 'Save changes'}
          </button>
          <button type="button" onClick={onClose} className="btn-secondary">Cancel</button>
        </div>
      </form>
    </SectionCard>
  )
}
