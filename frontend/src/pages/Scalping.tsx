import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { KillSwitch } from '../components/KillSwitch'
import { StrategyBuilder } from '../components/StrategyBuilder'
import { PageHeader, SectionCard } from '../components/ui/PageHeader'

export function ScalpingPage() {
  const qc = useQueryClient()
  const { data: strategies = [], isLoading } = useQuery({ queryKey: ['strategies'], queryFn: api.getStrategies })
  const { data: accounts = [] } = useQuery({ queryKey: ['accounts'], queryFn: api.getAccounts })

  const start = useMutation({
    mutationFn: api.startStrategy,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategies'] }),
  })
  const stop = useMutation({
    mutationFn: api.stopStrategy,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategies'] }),
  })

  return (
    <div className="p-6 lg:p-8 max-w-[1400px]">
      <PageHeader
        title="Scalping Terminal"
        subtitle="Hilega Milega strategy builder, execution controls, and fleet management"
      />

      <div className="grid xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          <StrategyBuilder accounts={accounts} />

          <SectionCard
            title="Active Strategies"
            description="Start in paper mode — validate before going live"
          >
            {isLoading ? (
              <p className="text-sm text-text-muted">Loading…</p>
            ) : strategies.length === 0 ? (
              <p className="text-sm text-text-muted py-4 text-center">
                No strategies yet. Use the builder above to create one.
              </p>
            ) : (
              <div className="space-y-3">
                {strategies.map((s) => (
                  <div
                    key={s.id}
                    className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-btn border border-border bg-bg-subtle/50"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold">{s.name}</h3>
                        <span className={`badge ${s.paper_mode ? 'bg-warn/10 text-warn' : 'bg-down/10 text-down'}`}>
                          {s.paper_mode ? 'PAPER' : 'LIVE'}
                        </span>
                        {s.running && <span className="badge bg-accent-50 text-accent">RUNNING</span>}
                      </div>
                      <p className="text-xs text-text-muted mt-1">
                        {s.symbol} · {s.entry_tf} / {s.htf} · Risk {s.risk_pct}% · R:R {s.rr_ratio}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      {s.running ? (
                        <button
                          onClick={() => stop.mutate(s.id)}
                          disabled={stop.isPending}
                          className="px-4 py-2 rounded-btn border border-down text-down text-sm font-semibold hover:bg-down/5"
                        >
                          Stop
                        </button>
                      ) : (
                        <button
                          onClick={() => start.mutate(s.id)}
                          disabled={start.isPending}
                          className="btn-accent py-2"
                        >
                          Start Engine
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>
        </div>

        <div className="space-y-6">
          <KillSwitch />

          <SectionCard title="Signal Pipeline" description="Decision flow per cycle">
            <ol className="space-y-2 text-sm text-text-muted">
              {[
                'Pre-checks & risk guards',
                'Regime filter (ATR, spread)',
                'Hilega Milega trigger',
                'MTF confirmation',
                'Anti-chase & sizing',
                'Bracket entry & manage',
              ].map((step, i) => (
                <li key={step} className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-primary-50 text-primary text-xs font-bold flex items-center justify-center shrink-0">
                    {i + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </SectionCard>

          <div className="card p-5 border-warn/30 bg-warn/5">
            <p className="text-sm font-semibold text-warn mb-1">Paper Mode Default</p>
            <p className="text-xs text-text-muted leading-relaxed">
              All new strategies start in paper mode. Switch to live only after validating signals and fills on one account.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
