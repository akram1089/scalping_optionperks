import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { useClock, useMarketStatus, formatISTTime } from '../../hooks/useMarketStatus'
import { useLiveStore } from '../../store'

interface Props {
  onMenuClick?: () => void
}

export function TopStatusBar({ onMenuClick }: Props) {
  const time = useClock()
  const market = useMarketStatus()
  const killSwitch = useLiveStore((s) => s.killSwitch)
  const wsConnected = useLiveStore((s) => s.wsConnected)
  const ticks = useLiveStore((s) => s.ticks)
  const tickCount = Object.keys(ticks).length

  const { data: killData } = useQuery({
    queryKey: ['kill-switch'],
    queryFn: api.getKillSwitch,
    refetchInterval: 15000,
  })

  const isKilled = killSwitch || killData?.kill_switch
  const streamLive = wsConnected && tickCount > 0
  const streamLabel = streamLive ? 'LIVE' : wsConnected ? 'WAITING' : 'OFFLINE'
  const streamOk = streamLive || (!market.open && wsConnected)

  return (
    <header className="sticky top-0 z-20 bg-surface/90 backdrop-blur-md border-b border-border px-4 py-2.5 sm:px-6 sm:py-3">
      <div className="flex flex-wrap items-center justify-between gap-2 sm:gap-3">
        <div className="flex flex-wrap items-center gap-2 min-w-0">
          {onMenuClick && (
            <button
              type="button"
              onClick={onMenuClick}
              aria-label="Open menu"
              className="lg:hidden p-2 -ml-1 rounded-btn border border-border bg-bg-subtle text-text-muted hover:text-text"
            >
              <MenuIcon />
            </button>
          )}
          <span className={`badge ${market.open ? 'bg-accent-50 text-accent' : 'bg-down/10 text-down'}`}>
            {market.label}
          </span>
          <StatusPill label="STREAM" value={streamLabel} ok={streamOk} compact />
          <StatusPill label="ORDERS" value={isKilled ? 'BLOCKED' : 'READY'} ok={!isKilled} compact />
          {isKilled && (
            <span className="badge bg-down text-white hidden sm:inline-flex">KILL SWITCH ON</span>
          )}
        </div>
        <div className="flex items-center gap-3 sm:gap-4 text-xs text-text-muted">
          <span className="hidden sm:inline">
            TICKS: <strong className="text-text">{tickCount}</strong>
          </span>
          <span className="font-mono tabular-nums text-[11px] sm:text-xs">{formatISTTime(time)} IST</span>
        </div>
      </div>
    </header>
  )
}

function StatusPill({
  label,
  value,
  ok,
  compact,
}: {
  label: string
  value: string
  ok: boolean
  compact?: boolean
}) {
  return (
    <div className="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1 sm:py-1.5 rounded-btn border border-border bg-bg-subtle text-[10px] sm:text-[11px]">
      {!compact && <span className="text-text-faint font-medium hidden md:inline">{label}</span>}
      <span className="text-text-faint font-medium md:hidden">{label.slice(0, 3)}</span>
      <span className={`font-semibold ${ok ? 'text-up' : 'text-down'}`}>{value}</span>
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${ok ? 'bg-up' : 'bg-down'}`} />
    </div>
  )
}

function MenuIcon() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
    </svg>
  )
}
