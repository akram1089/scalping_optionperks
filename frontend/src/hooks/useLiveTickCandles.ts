import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { appendTickToCandles, seedSecondCandlesFromClose } from '../charts/tickCandles'
import type { ChartCandle } from '../charts/TradingChart'
import { useLiveStore } from '../store'

/** Build live 1-second candles from WebSocket ticks for a chart symbol. */
export function useLiveTickCandles(
  instrumentToken: number,
  tradingsymbol: string,
  enabled: boolean,
  seedClose?: number,
) {
  const tick = useLiveStore((s) => s.ticksByToken[instrumentToken])
  const [candles, setCandles] = useState<ChartCandle[]>([])
  const subscribed = useRef(false)

  useEffect(() => {
    if (!enabled || !instrumentToken) return
    if (subscribed.current) return
    subscribed.current = true
    api
      .subscribeTicks([{ instrument_token: instrumentToken, tradingsymbol }])
      .catch(() => {})
  }, [enabled, instrumentToken, tradingsymbol])

  useEffect(() => {
    subscribed.current = false
    setCandles(seedClose ? seedSecondCandlesFromClose(seedClose) : [])
  }, [instrumentToken, seedClose])

  useEffect(() => {
    if (!enabled || !tick?.ltp) return
    setCandles((prev) => {
      const base =
        prev.length > 0
          ? prev
          : seedClose
            ? seedSecondCandlesFromClose(seedClose)
            : []
      return appendTickToCandles(base, tick.ltp!, tick.ts)
    })
  }, [enabled, tick?.ltp, tick?.ts, seedClose])

  return { candles, liveLtp: tick?.ltp }
}
