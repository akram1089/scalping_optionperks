import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { useLiveStore } from '../store'

/** Keep index ticks fresh — WebSocket is primary; this is a 2s safety net. */
export function useLiveTickPoll() {
  const setTick = useLiveStore((s) => s.setTick)
  const setStreamStatus = useLiveStore((s) => s.setStreamStatus)

  const { data: accounts = [] } = useQuery({
    queryKey: ['accounts'],
    queryFn: api.getAccounts,
    staleTime: 60_000,
  })
  const hasZerodha = accounts.some((a) => a.broker === 'zerodha' && a.session_active)

  useQuery({
    queryKey: ['tick-snapshot', hasZerodha],
    queryFn: async () => {
      const res = await api.getTickSnapshot()
      Object.values(res.ticks).forEach((t) => setTick(t))
      if (res.stream) setStreamStatus(res.stream)
      return res
    },
    enabled: hasZerodha,
    refetchInterval: 2_000,
  })
}
