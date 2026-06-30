import type { PnL } from '../api/client'
import { asNumber } from '../api/client'

interface Props {
  data: PnL[]
  accountLabels: Record<string, string>
}

export function PnLCards({ data, accountLabels }: Props) {
  if (data.length === 0) {
    return (
      <div className="text-sm text-text-muted">No P&L data yet.</div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {data.map((p) => {
        const total = asNumber(p.total_pnl)
        const up = total >= 0
        return (
          <div key={p.account_id} className="bg-bg-subtle rounded-card p-5 border border-border shadow-card">
            <div className="text-sm text-text-muted mb-1">
              {accountLabels[p.account_id] ?? p.account_id.slice(0, 8)}
            </div>
            <div className={`text-2xl font-bold ${up ? 'text-up' : 'text-down'}`}>
              ₹{total.toFixed(2)}
            </div>
            <div className="flex gap-4 mt-3 text-xs text-text-muted">
              <span>Trades: {p.trades_today}</span>
              <span className="text-up">W: {p.wins}</span>
              <span className="text-down">L: {p.losses}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
