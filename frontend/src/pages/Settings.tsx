import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { PageHeader, SectionCard } from '../components/ui/PageHeader'
import { useAuthStore, useLiveStore } from '../store'

export function SettingsPage() {
  const qc = useQueryClient()
  const email = useAuthStore((s) => s.email)
  const setKillSwitch = useLiveStore((s) => s.setKillSwitch)

  const { data: killData } = useQuery({ queryKey: ['kill-switch'], queryFn: api.getKillSwitch })
  const { data: audit = [] } = useQuery({ queryKey: ['audit'], queryFn: api.getAuditLog })
  const { data: instrumentSync } = useQuery({
    queryKey: ['instrument-sync'],
    queryFn: api.getInstrumentSyncStatus,
    refetchInterval: 30_000,
  })

  const resetKill = useMutation({
    mutationFn: api.resetKillSwitch,
    onSuccess: () => {
      setKillSwitch(false)
      qc.invalidateQueries({ queryKey: ['kill-switch'] })
    },
  })

  const syncInstruments = useMutation({
    mutationFn: api.triggerInstrumentSync,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['instrument-sync'] })
      qc.invalidateQueries({ queryKey: ['instruments'] })
    },
  })

  return (
    <div className="px-4 py-4 sm:p-6 lg:p-8 max-w-[900px]">
      <PageHeader title="Settings" subtitle="Account preferences, safety controls, and audit trail" />

      <div className="space-y-6">
        <SectionCard title="Profile">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between py-2 border-b border-border">
              <dt className="text-text-muted">Email</dt>
              <dd className="font-medium">{email ?? '—'}</dd>
            </div>
            <div className="flex justify-between py-2 border-b border-border">
              <dt className="text-text-muted">Platform</dt>
              <dd className="font-medium">ScalpDesk v0.1</dd>
            </div>
            <div className="flex justify-between py-2">
              <dt className="text-text-muted">Default Mode</dt>
              <dd><span className="badge bg-warn/10 text-warn">PAPER</span></dd>
            </div>
          </dl>
        </SectionCard>

        <SectionCard title="Safety Controls">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4">
            <div>
              <p className="font-semibold">Global Kill Switch</p>
              <p className="text-sm text-text-muted mt-0.5">
                {killData?.kill_switch
                  ? 'Active — all strategies halted. Reset when safe to resume.'
                  : 'Inactive — trading engines can run normally.'}
              </p>
            </div>
            {killData?.kill_switch && (
              <button
                onClick={() => resetKill.mutate()}
                disabled={resetKill.isPending}
                className="btn-secondary"
              >
                Reset Kill Switch
              </button>
            )}
          </div>
        </SectionCard>

        <SectionCard title="Instrument Master" description="Zerodha symbols — auto-sync daily at 08:50 IST">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4">
            <div className="text-sm space-y-1">
              {instrumentSync ? (
                <>
                  <p>
                    Last sync:{' '}
                    <span className={`font-semibold ${instrumentSync.status === 'success' ? 'text-up' : instrumentSync.status === 'failed' ? 'text-down' : 'text-warn'}`}>
                      {instrumentSync.status.toUpperCase()}
                    </span>
                    {' · '}{instrumentSync.source}
                  </p>
                  <p className="text-text-muted text-xs">
                    {instrumentSync.rows_upserted.toLocaleString()} upserted
                    {instrumentSync.finished_at && ` · ${new Date(instrumentSync.finished_at).toLocaleString('en-IN')}`}
                  </p>
                  {instrumentSync.error_detail && (
                    <p className="text-down text-xs">{instrumentSync.error_detail}</p>
                  )}
                </>
              ) : (
                <p className="text-text-muted">No sync run yet. Trigger manually after VPS deploy.</p>
              )}
            </div>
            <button
              onClick={() => syncInstruments.mutate()}
              disabled={syncInstruments.isPending}
              className="btn-primary py-2"
            >
              {syncInstruments.isPending ? 'Syncing…' : 'Sync Now'}
            </button>
          </div>
        </SectionCard>

        <SectionCard title="Kite Redirect URL" description="Set this in your Kite developer app">
          <code className="block p-3 rounded-btn bg-bg-subtle text-sm font-mono text-primary break-all">
            http://localhost:8000/accounts/callback
          </code>
        </SectionCard>

        <SectionCard title="Audit Log" description="Recent platform actions">
          {audit.length === 0 ? (
            <p className="text-sm text-text-muted text-center py-6">No audit entries yet</p>
          ) : (
            <div className="overflow-x-auto -mx-5">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wider text-text-faint border-b border-border">
                    <th className="px-5 py-2 font-semibold">Time</th>
                    <th className="px-5 py-2 font-semibold">Action</th>
                    <th className="px-5 py-2 font-semibold">Target</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.slice(0, 20).map((entry) => (
                    <tr key={entry.id} className="border-b border-border/60">
                      <td className="px-5 py-2.5 text-text-muted tabular-nums">
                        {new Date(entry.ts).toLocaleString('en-IN')}
                      </td>
                      <td className="px-5 py-2.5 font-medium">{entry.action}</td>
                      <td className="px-5 py-2.5 text-text-muted truncate max-w-[200px]">{entry.target}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  )
}
