import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, asNumber } from '../api/client'
import { IndexCard, PageHeader, SectionCard, StatCard, ActionBadge } from '../components/ui/PageHeader'
import { PositionsTable } from '../components/PositionsTable'
import { useLiveStore } from '../store'

const INDEX_SYMBOLS = ['NIFTY 50', 'BANK NIFTY', 'SENSEX']

export function DashboardPage() {
  const selectedAccountId = useLiveStore((s) => s.selectedAccountId)
  const setSelectedAccount = useLiveStore((s) => s.setSelectedAccount)
  const ticks = useLiveStore((s) => s.ticks)
  const streamStatus = useLiveStore((s) => s.streamStatus)
  const killSwitch = useLiveStore((s) => s.killSwitch)
  const [signalFilter, setSignalFilter] = useState('ALL')

  const { data: accounts = [] } = useQuery({ queryKey: ['accounts'], queryFn: api.getAccounts })
  const { data: positions = [] } = useQuery({
    queryKey: ['positions', selectedAccountId],
    queryFn: () => api.getPositions(selectedAccountId ?? undefined),
    refetchInterval: 10000,
  })
  const { data: pnl = [] } = useQuery({
    queryKey: ['pnl', selectedAccountId],
    queryFn: () => api.getPnL(selectedAccountId ?? undefined),
    refetchInterval: 10000,
  })
  const { data: signals = [] } = useQuery({
    queryKey: ['signals'],
    queryFn: () => api.getSignals(),
    refetchInterval: 15000,
  })
  const { data: strategies = [] } = useQuery({ queryKey: ['strategies'], queryFn: api.getStrategies })
  const { data: killData } = useQuery({ queryKey: ['kill-switch'], queryFn: api.getKillSwitch })
  const isKilled = killSwitch || killData?.kill_switch
  const { data: trades = [] } = useQuery({
    queryKey: ['trades', selectedAccountId],
    queryFn: () => api.getTrades(selectedAccountId ?? undefined),
    refetchInterval: 15000,
  })

  const totals = useMemo(() => {
    const realized = pnl.reduce((s, p) => s + asNumber(p.realized_pnl), 0)
    const wins = pnl.reduce((s, p) => s + asNumber(p.wins), 0)
    const losses = pnl.reduce((s, p) => s + asNumber(p.losses), 0)
    const tradesToday = pnl.reduce((s, p) => s + asNumber(p.trades_today), 0)
    const buySignals = signals.filter((s) => s.side === 'BUY').length
    const sellSignals = signals.filter((s) => s.side === 'SELL').length
    const running = strategies.filter((s) => s.running).length
    return { realized, wins, losses, tradesToday, buySignals, sellSignals, running }
  }, [pnl, signals, strategies])

  const filteredSignals = signals.filter((s) => {
    if (signalFilter === 'ALL') return true
    return s.side === signalFilter
  })

  return (
    <div className="px-4 py-4 sm:p-6 lg:p-8 max-w-[1600px]">
      <PageHeader
        title="Trading Dashboard"
        subtitle="Institutional-grade intraday analytics and execution terminal"
        action={
          <div className="flex flex-wrap gap-2">
            <AccountChip label="All" active={!selectedAccountId} onClick={() => setSelectedAccount(null)} />
            {accounts.map((a) => (
              <AccountChip
                key={a.id}
                label={a.label}
                active={selectedAccountId === a.id}
                live={a.session_active}
                onClick={() => setSelectedAccount(a.id)}
              />
            ))}
          </div>
        }
      />

        {isKilled && (
          <div className="mb-4 p-3 rounded-btn bg-down/10 text-down text-sm">
            Kill switch is ON — new orders are blocked. Reset it in Settings to trade. Live data is unaffected.
          </div>
        )}
        {!Object.keys(ticks).length && streamStatus?.message && (
          <div className="mb-4 p-3 rounded-btn bg-warn/10 text-warn text-sm">
            {streamStatus.message}
            {streamStatus.reason === 'no_instruments' && (
              <> — go to <strong>Settings → Sync Instruments</strong>, then refresh.</>
            )}
            {streamStatus.reason === 'no_session' && (
              <> — go to <strong>Accounts</strong> and connect Zerodha.</>
            )}
          </div>
        )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 mb-6">
        {INDEX_SYMBOLS.map((sym) => {
          const tick = ticks[sym]
          return (
            <IndexCard
              key={sym}
              symbol={sym}
              price={tick?.ltp}
              change={tick?.change_pct}
              delayed={!tick?.ltp || (tick.ts != null && Date.now() / 1000 - tick.ts > 30)}
            />
          )
        })}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2 sm:gap-3 mb-6 sm:mb-8">
        <StatCard label="Active" value={`${totals.running} / ${strategies.length}`} accent="blue" />
        <StatCard label="Buy Signals" value={totals.buySignals} accent="green" />
        <StatCard label="Sell Signals" value={totals.sellSignals} accent="red" />
        <StatCard label="Open Pos" value={positions.length} accent="slate" />
        <StatCard label="Trades Today" value={totals.tradesToday} accent="slate" />
        <StatCard label="Wins" value={totals.wins} accent="green" />
        <StatCard label="Losses" value={totals.losses} accent="red" />
        <StatCard
          label="P&L Today"
          value={`₹${totals.realized.toFixed(0)}`}
          trend={totals.realized >= 0 ? 'up' : 'down'}
        />
      </div>

      <div className="grid xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2">
          <SectionCard
            title="Priority Signals"
            description="Ranked by recency — Aladin crossover triggers"
            icon={<TrendIcon />}
            action={
              <div className="flex gap-1">
                {['ALL', 'BUY', 'SELL'].map((f) => (
                  <button
                    key={f}
                    onClick={() => setSignalFilter(f)}
                    className={`px-3 py-1 text-xs font-semibold rounded-pill transition-colors ${
                      signalFilter === f ? 'bg-primary-navy text-white' : 'text-text-muted hover:bg-bg-subtle'
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>
            }
          >
            <div className="overflow-x-auto -mx-5">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wider text-text-faint border-b border-border">
                    <th className="px-5 py-3 font-semibold">Time</th>
                    <th className="px-5 py-3 font-semibold">Symbol</th>
                    <th className="px-5 py-3 font-semibold text-right">Price</th>
                    <th className="px-5 py-3 font-semibold">Action</th>
                    <th className="px-5 py-3 font-semibold">RSI</th>
                    <th className="px-5 py-3 font-semibold">Mode</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSignals.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-5 py-10 text-center text-text-muted">
                        No signals yet — start a strategy in Scalping
                      </td>
                    </tr>
                  ) : (
                    filteredSignals.slice(0, 12).map((sig) => (
                      <tr key={sig.id} className="border-b border-border/60 hover:bg-bg-subtle/50">
                        <td className="px-5 py-3 text-text-muted tabular-nums">
                          {new Date(sig.ts).toLocaleTimeString('en-IN')}
                        </td>
                        <td className="px-5 py-3 font-semibold">
                          {strategies.find((s) => s.id === sig.strategy_id)?.symbol ?? '—'}
                        </td>
                        <td className="px-5 py-3 text-right font-mono tabular-nums">₹{sig.price}</td>
                        <td className="px-5 py-3"><ActionBadge side={sig.side} /></td>
                        <td className="px-5 py-3 text-text-muted">
                          {sig.indicator_snapshot_json?.rsi?.toFixed(1) ?? '—'}
                        </td>
                        <td className="px-5 py-3">
                          <span className={`badge ${sig.paper ? 'bg-warn/10 text-warn' : 'bg-accent-50 text-accent'}`}>
                            {sig.paper ? 'PAPER' : 'LIVE'}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>

        <div className="space-y-6">
          <SectionCard title="Recent Trades" description="Closed positions today">
            {trades.length === 0 ? (
              <p className="text-sm text-text-muted text-center py-6">No trades yet</p>
            ) : (
              <ul className="space-y-3">
                {trades.slice(0, 6).map((t) => (
                  <li key={t.id} className="flex items-center justify-between text-sm">
                    <div>
                      <span className="font-semibold">{t.symbol}</span>
                      <span className="text-text-faint ml-2">{t.side}</span>
                    </div>
                    <span className={`font-bold tabular-nums ${asNumber(t.pnl) >= 0 ? 'text-up' : 'text-down'}`}>
                      {t.pnl != null ? `₹${asNumber(t.pnl).toFixed(0)}` : '—'}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard title="Open Positions" description={`${positions.length} active`}>
            <PositionsTable positions={positions} compact />
          </SectionCard>
        </div>
      </div>
    </div>
  )
}

function AccountChip({
  label,
  active,
  live,
  onClick,
}: {
  label: string
  active: boolean
  live?: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-pill text-sm font-medium border transition-colors ${
        active
          ? 'bg-primary-navy text-white border-primary-navy'
          : 'border-border text-text-muted hover:border-border-strong'
      }`}
    >
      {label}
      {live && <span className="ml-1.5 w-1.5 h-1.5 inline-block rounded-full bg-up" />}
    </button>
  )
}

function TrendIcon() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M3 17l6-6 4 4 8-10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
