import { useLiveStore } from '../store'

const DEFAULT_SYMBOLS = ['NIFTY 50', 'SBIN', 'INFY', 'RELIANCE', 'TCS']

export function TickerBar() {
  const ticks = useLiveStore((s) => s.ticks)

  return (
    <div className="bg-primary-navy text-white overflow-hidden">
      <div className="flex animate-scroll whitespace-nowrap py-2 px-4 gap-8">
        {DEFAULT_SYMBOLS.map((sym) => {
          const tick = ticks[sym]
          const ltp = tick?.ltp ?? '—'
          const chg = tick?.change_pct ?? 0
          const up = chg >= 0
          return (
            <span key={sym} className="inline-flex items-center gap-2 text-sm font-medium">
              <span className="text-white/80">{sym}</span>
              <span>{typeof ltp === 'number' ? ltp.toFixed(2) : ltp}</span>
              <span className={up ? 'text-up' : 'text-down'}>
                {typeof chg === 'number' ? `${up ? '+' : ''}${chg.toFixed(2)}%` : ''}
              </span>
            </span>
          )
        })}
      </div>
      <style>{`
        @keyframes scroll { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
        .animate-scroll { animation: scroll 30s linear infinite; }
      `}</style>
    </div>
  )
}
