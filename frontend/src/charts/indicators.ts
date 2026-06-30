/** Hilega Milega indicators — mirrors backend app/engine/indicators.py */

export interface IndicatorParams {
  rsiLength: number
  wmaLength: number
  emaLength: number
  midLevel: number
}

export const DEFAULT_INDICATOR_PARAMS: IndicatorParams = {
  rsiLength: 14,
  wmaLength: 21,
  emaLength: 3,
  midLevel: 50,
}

export function computeRsi(closes: number[], length: number): number[] {
  const rsi = Array(closes.length).fill(NaN)
  if (closes.length < length + 1) return rsi

  const deltas = closes.slice(1).map((c, i) => c - closes[i])
  let avgGain = 0
  let avgLoss = 0
  for (let i = 0; i < length; i++) {
    const d = deltas[i]
    if (d > 0) avgGain += d
    else avgLoss += -d
  }
  avgGain /= length
  avgLoss /= length

  rsi[length] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss)

  for (let i = length + 1; i < closes.length; i++) {
    const d = deltas[i - 1]
    avgGain = (avgGain * (length - 1) + Math.max(d, 0)) / length
    avgLoss = (avgLoss * (length - 1) + Math.max(-d, 0)) / length
    rsi[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss)
  }
  return rsi
}

export function computeWma(values: number[], length: number): number[] {
  const out = Array(values.length).fill(NaN)
  const weights = Array.from({ length }, (_, i) => i + 1)
  const wSum = weights.reduce((a, b) => a + b, 0)
  for (let i = length - 1; i < values.length; i++) {
    const window = values.slice(i - length + 1, i + 1)
    if (window.some((v) => Number.isNaN(v))) continue
    out[i] = window.reduce((sum, v, j) => sum + v * weights[j], 0) / wSum
  }
  return out
}

export function computeEma(values: number[], length: number): number[] {
  const out = Array(values.length).fill(NaN)
  const alpha = 2 / (length + 1)
  let start = values.findIndex((v) => !Number.isNaN(v))
  if (start < 0) return out
  out[start] = values[start]
  for (let i = start + 1; i < values.length; i++) {
    out[i] = Number.isNaN(values[i]) ? out[i - 1] : alpha * values[i] + (1 - alpha) * out[i - 1]
  }
  return out
}

export function computeHilegaMilega(closes: number[], params: IndicatorParams) {
  const rsi = computeRsi(closes, params.rsiLength)
  const hilega = computeWma(rsi, params.wmaLength)
  const milega = computeEma(rsi, params.emaLength)
  return { rsi, hilega, milega }
}

export interface SignalMarker {
  time: number
  side: 'BUY' | 'SELL'
}

/** Detect Hilega Milega crossover signals on chart bars */
export function detectSignals(
  times: number[],
  closes: number[],
  params: IndicatorParams,
): SignalMarker[] {
  const { hilega, milega } = computeHilegaMilega(closes, params)
  const signals: SignalMarker[] = []
  for (let i = 1; i < closes.length; i++) {
    if (Number.isNaN(hilega[i]) || Number.isNaN(milega[i])) continue
    const pm = milega[i - 1]
    const ph = hilega[i - 1]
    const m = milega[i]
    const h = hilega[i]
    const longCross = pm <= ph && m > h && m > params.midLevel && h > params.midLevel
    const shortCross = pm >= ph && m < h && m < params.midLevel && h < params.midLevel
    if (longCross) signals.push({ time: times[i], side: 'BUY' })
    if (shortCross) signals.push({ time: times[i], side: 'SELL' })
  }
  return signals
}
