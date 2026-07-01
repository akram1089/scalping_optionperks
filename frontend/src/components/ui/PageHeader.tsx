interface PageHeaderProps {
  title: string
  subtitle?: string
  action?: React.ReactNode
}

export function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 sm:gap-4 mb-6 sm:mb-8">
      <div>
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function StatCard({
  label,
  value,
  sub,
  trend,
  accent,
}: {
  label: string
  value: string | number
  sub?: string
  trend?: 'up' | 'down' | 'neutral'
  accent?: 'green' | 'red' | 'blue' | 'amber' | 'slate'
}) {
  const accentMap = {
    green: 'text-up',
    red: 'text-down',
    blue: 'text-primary',
    amber: 'text-warn',
    slate: 'text-text',
  }
  return (
    <div className="card p-4 min-w-[120px]">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-text-faint mb-1">{label}</p>
      <p className={`text-2xl font-bold tabular-nums ${accent ? accentMap[accent] : trend === 'up' ? 'text-up' : trend === 'down' ? 'text-down' : 'text-text'}`}>
        {value}
      </p>
      {sub && <p className="text-xs text-text-muted mt-1">{sub}</p>}
    </div>
  )
}

export function IndexCard({
  symbol,
  price,
  change,
  delayed,
}: {
  symbol: string
  price?: number
  change?: number
  delayed?: boolean
}) {
  const up = (change ?? 0) >= 0
  return (
    <div className="card p-4 sm:p-5 flex-1 min-w-0 sm:min-w-[140px]">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-bold text-text-faint tracking-wider">{symbol}</span>
        {delayed && <span className="badge bg-bg-subtle text-text-faint">DELAYED</span>}
      </div>
      <p className="text-2xl font-bold tabular-nums">
        {price != null ? `₹${price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '—'}
      </p>
      {change != null && (
        <p className={`text-sm font-semibold mt-1 ${up ? 'text-up' : 'text-down'}`}>
          {up ? '+' : ''}{change.toFixed(2)}%
        </p>
      )}
    </div>
  )
}

export function SectionCard({
  title,
  description,
  icon,
  children,
  action,
}: {
  title: string
  description?: string
  icon?: React.ReactNode
  children: React.ReactNode
  action?: React.ReactNode
}) {
  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          {icon && <div className="mt-0.5 text-text-muted">{icon}</div>}
          <div>
            <h2 className="font-display font-bold text-sm uppercase tracking-wide text-primary-navy">{title}</h2>
            {description && <p className="text-xs text-text-muted mt-0.5">{description}</p>}
          </div>
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </div>
  )
}

export function ActionBadge({ side }: { side: string }) {
  const isBuy = side === 'BUY' || side.includes('BUY')
  const isSell = side === 'SELL' || side.includes('SELL')
  if (isBuy) return <span className="badge bg-accent-50 text-accent">{side}</span>
  if (isSell) return <span className="badge bg-down/10 text-down">{side}</span>
  return <span className="badge bg-bg-subtle text-text-muted">{side}</span>
}
