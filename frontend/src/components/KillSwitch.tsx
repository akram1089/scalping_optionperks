import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { useLiveStore } from '../store'

export function KillSwitch() {
  const qc = useQueryClient()
  const killSwitch = useLiveStore((s) => s.killSwitch)
  const setKillSwitch = useLiveStore((s) => s.setKillSwitch)

  const activate = useMutation({
    mutationFn: api.killSwitch,
    onSuccess: () => {
      setKillSwitch(true)
      qc.invalidateQueries({ queryKey: ['strategies'] })
      qc.invalidateQueries({ queryKey: ['kill-switch'] })
    },
  })

  return (
    <div className="card border-down/20 overflow-hidden">
      <div className="px-5 py-4 bg-down/5 border-b border-down/10">
        <h3 className="font-display font-bold text-sm uppercase tracking-wide text-down">Emergency Kill Switch</h3>
        <p className="text-xs text-text-muted mt-1">
          Halts all strategies and squares off open positions immediately.
        </p>
      </div>
      <div className="p-5">
        {killSwitch ? (
          <div className="px-4 py-4 bg-down text-white rounded-btn font-bold text-center text-sm uppercase tracking-wider">
            Kill Switch Active
          </div>
        ) : (
          <button
            onClick={() => {
              if (confirm('Activate kill switch? This will stop ALL trading and flatten positions.')) {
                activate.mutate()
              }
            }}
            disabled={activate.isPending}
            className="w-full py-4 rounded-btn bg-down text-white font-bold text-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {activate.isPending ? 'Activating…' : 'KILL SWITCH'}
          </button>
        )}
        <p className="text-[11px] text-text-faint mt-3 text-center">Reset in Settings after resolving the issue</p>
      </div>
    </div>
  )
}
