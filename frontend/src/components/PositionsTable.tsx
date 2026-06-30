import type { Position } from '../api/client'
import { asNumber } from '../api/client'

interface Props {
  positions: Position[]
  compact?: boolean
}

export function PositionsTable({ positions, compact }: Props) {
  if (positions.length === 0) {
    return (
      <div className="text-sm text-text-muted py-6 text-center">
        No open positions
      </div>
    )
  }

  if (compact) {
    return (
      <ul className="space-y-2">
        {positions.map((p) => (
          <li key={p.id} className="flex items-center justify-between text-sm py-2 border-b border-border/60 last:border-0">
            <div>
              <span className="font-semibold">{p.symbol}</span>
              <span className={`ml-2 text-xs ${p.side === 'BUY' ? 'text-up' : 'text-down'}`}>{p.side}</span>
            </div>
            <span className="font-mono tabular-nums">{p.qty} @ ₹{asNumber(p.avg_price).toFixed(2)}</span>
          </li>
        ))}
      </ul>
    )
  }

  return (
    <div className="overflow-x-auto rounded-card border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wider text-text-faint bg-bg-subtle border-b border-border">
            <th className="px-4 py-3 font-semibold">Symbol</th>
            <th className="px-4 py-3 font-semibold">Side</th>
            <th className="px-4 py-3 font-semibold text-right">Qty</th>
            <th className="px-4 py-3 font-semibold text-right">Avg</th>
            <th className="px-4 py-3 font-semibold text-right">SL</th>
            <th className="px-4 py-3 font-semibold text-right">Target</th>
            <th className="px-4 py-3 font-semibold text-center">Mode</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => (
            <tr key={p.id} className="border-b border-border/60 hover:bg-bg-subtle/40">
              <td className="px-4 py-3 font-semibold">{p.symbol}</td>
              <td className={`px-4 py-3 font-medium ${p.side === 'BUY' ? 'text-up' : 'text-down'}`}>{p.side}</td>
              <td className="px-4 py-3 text-right tabular-nums">{p.qty}</td>
              <td className="px-4 py-3 text-right font-mono tabular-nums">{asNumber(p.avg_price).toFixed(2)}</td>
              <td className="px-4 py-3 text-right font-mono tabular-nums">{p.stop_loss != null ? asNumber(p.stop_loss).toFixed(2) : '—'}</td>
              <td className="px-4 py-3 text-right font-mono tabular-nums">{p.target != null ? asNumber(p.target).toFixed(2) : '—'}</td>
              <td className="px-4 py-3 text-center">
                <span className={`badge ${p.paper ? 'bg-warn/10 text-warn' : 'bg-accent-50 text-accent'}`}>
                  {p.paper ? 'PAPER' : 'LIVE'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
