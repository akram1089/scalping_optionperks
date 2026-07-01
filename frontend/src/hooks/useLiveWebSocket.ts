import { useEffect } from 'react'
import { api, getWsUrl } from '../api/client'
import { useLiveStore } from '../store'

const RECONNECT_MS = 3000

export function useLiveWebSocket() {
  const setTick = useLiveStore((s) => s.setTick)
  const setWsConnected = useLiveStore((s) => s.setWsConnected)

  useEffect(() => {
    let ws: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined
    let pingTimer: ReturnType<typeof setInterval> | undefined
    let cancelled = false

    const hydrateTicks = () => {
      api.getTickSnapshot().then((res) => {
        Object.values(res.ticks).forEach((tick) => setTick(tick))
      }).catch(() => {})
    }

    const connect = () => {
      if (cancelled) return
      hydrateTicks()
      ws = new WebSocket(getWsUrl())

      ws.onopen = () => setWsConnected(true)
      ws.onclose = () => {
        setWsConnected(false)
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, RECONNECT_MS)
        }
      }
      ws.onerror = () => ws?.close()

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type === 'tick' && msg.data) {
            setTick(msg.data)
          }
        } catch {
          /* ignore */
        }
      }

      pingTimer = setInterval(() => {
        if (ws?.readyState === WebSocket.OPEN) ws.send('ping')
      }, 30000)
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (pingTimer) clearInterval(pingTimer)
      setWsConnected(false)
      ws?.close()
    }
  }, [setTick, setWsConnected])
}
