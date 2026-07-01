import type { ChartCandle } from './TradingChart'

/** Append an LTP tick into 1-second OHLC candles. */
export function appendTickToCandles(
  candles: ChartCandle[],
  ltp: number,
  tsSec?: number,
): ChartCandle[] {
  const bucket = Math.floor(tsSec ?? Date.now() / 1000)
  const last = candles[candles.length - 1]

  if (last && last.time === bucket) {
    const updated: ChartCandle = {
      ...last,
      high: Math.max(last.high, ltp),
      low: Math.min(last.low, ltp),
      close: ltp,
    }
    return [...candles.slice(0, -1), updated]
  }

  const next: ChartCandle = {
    time: bucket,
    open: ltp,
    high: ltp,
    low: ltp,
    close: ltp,
    volume: 0,
  }
  const merged = [...candles, next]
  return merged.length > 600 ? merged.slice(-600) : merged
}

/** Seed 1s series from the close of the latest historical bar. */
export function seedSecondCandlesFromClose(close: number, count = 60): ChartCandle[] {
  const now = Math.floor(Date.now() / 1000)
  const out: ChartCandle[] = []
  for (let i = count; i > 0; i--) {
    const t = now - i
    out.push({ time: t, open: close, high: close, low: close, close, volume: 0 })
  }
  return out
}
