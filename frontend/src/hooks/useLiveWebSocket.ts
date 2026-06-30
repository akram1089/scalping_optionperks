import { useEffect, useRef } from 'react'
import { getWsUrl } from '../api/client'
import { useLiveStore } from '../store'

export function useLiveWebSocket() {
  const setTick = useLiveStore((s) => s.setTick)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const ws = new WebSocket(getWsUrl())
    wsRef.current = ws

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

    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 30000)

    return () => {
      clearInterval(ping)
      ws.close()
    }
  }, [setTick])
}
