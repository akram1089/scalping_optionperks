import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { useClock, useMarketStatus, formatISTTime } from '../../hooks/useMarketStatus'
import { useLiveStore } from '../../store'

export function TopStatusBar() {
  const time = useClock()
  const market = useMarketStatus()
  const killSwitch = useLiveStore((s) => s.killSwitch)
  const ticks = useLiveStore((s) => s.ticks)
  const tickCount = Object.keys(ticks).length

  const { data: killData } = useQuery({
    queryKey: ['kill-switch'],
    queryFn: api.getKillSwitch,
    refetchInterval: 15000,
  })

  const isKilled = killSwitch || killData?.kill_switch

  return (
    <header className="sticky top-0 z-20 bg-surface/90 backdrop-blur-md border-b border-border px-6 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`badge ${market.open ? 'bg-accent-50 text-accent' : 'bg-down/10 text-down'}`}>
            {market.label}
          </span>
          <StatusPill label="MARKET STREAM" value="LIVE" ok />
          <StatusPill label="KITE API" value={isKilled ? 'HALTED' : 'READY'} ok={!isKilled} />
          {isKilled && (
            <span className="badge bg-down text-white">KILL SWITCH ON</span>
          )}
        </div>
        <div className="flex items-center gap-4 text-xs text-text-muted">
          <span>TICKS: <strong className="text-text">{tickCount}</strong></span>
          <span className="font-mono tabular-nums">{formatISTTime(time)} IST</span>
        </div>
      </div>
    </header>
  )
}

function StatusPill({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-btn border border-border bg-bg-subtle text-[11px]">
      <span className="text-text-faint font-medium">{label}</span>
      <span className={`font-semibold ${ok ? 'text-up' : 'text-down'}`}>{value}</span>
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-up' : 'bg-down'}`} />
    </div>
  )
}
