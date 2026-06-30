import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

export function StrategiesPage() {
  const qc = useQueryClient()
  const { data: strategies = [], isLoading } = useQuery({ queryKey: ['strategies'], queryFn: api.getStrategies })

  const start = useMutation({
    mutationFn: api.startStrategy,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategies'] }),
  })
  const stop = useMutation({
    mutationFn: api.stopStrategy,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategies'] }),
  })

  if (isLoading) return <div className="p-8 text-text-muted">Loading…</div>

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Strategies</h1>
      <div className="space-y-4">
        {strategies.length === 0 ? (
          <p className="text-text-muted">Create a strategy from the Dashboard.</p>
        ) : (
          strategies.map((s) => (
            <div key={s.id} className="bg-bg-subtle rounded-card p-5 border border-border shadow-card flex flex-wrap items-center justify-between gap-4">
              <div>
                <h3 className="font-semibold">{s.name}</h3>
                <p className="text-sm text-text-muted">
                  {s.symbol} · {s.entry_tf} / {s.htf} · Risk {s.risk_pct}% · R:R {s.rr_ratio}
                </p>
                <span className={`inline-block mt-2 text-xs px-2 py-0.5 rounded-full ${s.paper_mode ? 'bg-warn/20 text-warn' : 'bg-down/20 text-down'}`}>
                  {s.paper_mode ? 'PAPER MODE' : 'LIVE'}
                </span>
              </div>
              <div className="flex gap-2">
                {s.running ? (
                  <button
                    onClick={() => stop.mutate(s.id)}
                    className="px-4 py-2 rounded-btn border border-down text-down text-sm font-medium hover:bg-down/5"
                  >
                    Stop
                  </button>
                ) : (
                  <button
                    onClick={() => start.mutate(s.id)}
                    className="px-4 py-2 rounded-btn bg-accent text-white text-sm font-medium hover:bg-accent-700"
                  >
                    Start
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
      <div className="mt-8 p-4 bg-warn/10 border border-warn/30 rounded-card text-sm text-text-muted">
        <strong className="text-warn">Always start in PAPER mode.</strong> Validate on one account before going live.
      </div>
    </div>
  )
}
