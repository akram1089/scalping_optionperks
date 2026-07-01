import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { useLiveStore } from '../store'

/** Poll tick snapshot when WebSocket has not delivered data yet. */
export function useLiveTickPoll() {
  const tickCount = useLiveStore((s) => Object.keys(s.ticks).length)
  const setTick = useLiveStore((s) => s.setTick)
  const setStreamStatus = useLiveStore((s) => s.setStreamStatus)

  const { data: accounts = [] } = useQuery({
    queryKey: ['accounts'],
    queryFn: api.getAccounts,
    staleTime: 60_000,
  })
  const hasZerodha = accounts.some((a) => a.broker === 'zerodha' && a.session_active)

  useQuery({
    queryKey: ['tick-snapshot', tickCount, hasZerodha],
    queryFn: async () => {
      const res = await api.getTickSnapshot()
      Object.values(res.ticks).forEach((t) => setTick(t))
      if (res.stream) setStreamStatus(res.stream)
      return res
    },
    enabled: hasZerodha,
    refetchInterval: tickCount > 0 ? 15_000 : 3_000,
  })

  useEffect(() => {
    if (!hasZerodha || tickCount > 0) return
    const kick = setInterval(() => {
      api.refreshTicks().then((res) => {
        Object.values(res.ticks).forEach((t) => setTick(t))
        if (res.stream) setStreamStatus(res.stream)
      }).catch(() => {})
    }, 30_000)
    return () => clearInterval(kick)
  }, [hasZerodha, tickCount, setTick, setStreamStatus])
}
