import { useEffect, useRef } from 'react'
import {
  createChart,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from 'lightweight-charts'
import {
  computeAladin,
  detectSignals,
  type IndicatorParams,
} from './indicators'

export interface ChartCandle {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume?: number
}

export interface PriceLevels {
  entry?: number
  stopLoss?: number
  target?: number
}

interface Props {
  candles: ChartCandle[]
  symbol: string
  interval: string
  live?: boolean
  showSeconds?: boolean
  params: IndicatorParams
  levels: PriceLevels
  showSignals?: boolean
}

const CHART_OPTS = {
  layout: { background: { color: '#FFFFFF' }, textColor: '#64748B' },
  grid: { vertLines: { color: '#E8ECF1' }, horzLines: { color: '#E8ECF1' } },
  rightPriceScale: { borderColor: '#E8ECF1' },
  timeScale: { borderColor: '#E8ECF1', timeVisible: true, secondsVisible: false },
}

export function TradingChart({
  candles,
  symbol,
  interval,
  live = false,
  showSeconds = false,
  params,
  levels,
  showSignals = true,
}: Props) {
  const mainRef = useRef<HTMLDivElement>(null)
  const rsiRef = useRef<HTMLDivElement>(null)
  const mainChart = useRef<IChartApi | null>(null)
  const rsiChart = useRef<IChartApi | null>(null)
  const candleSeries = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const rsiSeries = useRef<ISeriesApi<'Line'> | null>(null)
  const signalSeries = useRef<ISeriesApi<'Line'> | null>(null)
  const fastSeries = useRef<ISeriesApi<'Line'> | null>(null)
  const midSeries = useRef<ISeriesApi<'Line'> | null>(null)
  const priceLines = useRef<IPriceLine[]>([])

  useEffect(() => {
    if (!mainRef.current || !rsiRef.current) return

    const main = createChart(mainRef.current, { ...CHART_OPTS, height: 380, width: mainRef.current.clientWidth })
    const rsi = createChart(rsiRef.current, { ...CHART_OPTS, height: 140, width: rsiRef.current.clientWidth })

    candleSeries.current = main.addCandlestickSeries({
      upColor: '#16A34A',
      downColor: '#DC2626',
      borderVisible: false,
      wickUpColor: '#16A34A',
      wickDownColor: '#DC2626',
    })

    rsiSeries.current = rsi.addLineSeries({ color: '#94A3B8', lineWidth: 1, title: 'RSI' })
    signalSeries.current = rsi.addLineSeries({ color: '#2563EB', lineWidth: 2, title: 'Aladin WMA' })
    fastSeries.current = rsi.addLineSeries({ color: '#D97706', lineWidth: 2, title: 'Aladin Fast' })
    midSeries.current = rsi.addLineSeries({ color: '#CBD5E1', lineWidth: 1, lineStyle: 2, title: '50' })

    mainChart.current = main
    rsiChart.current = rsi

    const onResize = () => {
      if (mainRef.current) main.applyOptions({ width: mainRef.current.clientWidth })
      if (rsiRef.current) rsi.applyOptions({ width: rsiRef.current.clientWidth })
    }
    window.addEventListener('resize', onResize)

    return () => {
      window.removeEventListener('resize', onResize)
      main.remove()
      rsi.remove()
      mainChart.current = null
      rsiChart.current = null
      candleSeries.current = null
      priceLines.current = []
    }
  }, [])

  useEffect(() => {
    if (!candleSeries.current || candles.length === 0) return

    const ohlc = candles.map((c) => ({
      time: c.time as Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }))
    candleSeries.current.setData(ohlc)

    for (const pl of priceLines.current) {
      candleSeries.current.removePriceLine(pl)
    }
    priceLines.current = []
    const addLine = (price: number | undefined, color: string, title: string) => {
      if (price == null || !candleSeries.current) return
      priceLines.current.push(
        candleSeries.current.createPriceLine({
          price,
          color,
          lineWidth: 2,
          lineStyle: 2,
          axisLabelVisible: true,
          title,
        }),
      )
    }
    addLine(levels.entry, '#2563EB', 'ENTRY')
    addLine(levels.stopLoss, '#DC2626', 'SL')
    addLine(levels.target, '#16A34A', 'TARGET')

    if (showSignals) {
      const times = candles.map((c) => c.time)
      const closes = candles.map((c) => c.close)
      const signals = detectSignals(times, closes, params)
      candleSeries.current.setMarkers(
        signals.map((s) => ({
          time: s.time as Time,
          position: s.side === 'BUY' ? 'belowBar' : 'aboveBar',
          color: s.side === 'BUY' ? '#16A34A' : '#DC2626',
          shape: s.side === 'BUY' ? 'arrowUp' : 'arrowDown',
          text: s.side,
        })) as SeriesMarker<Time>[],
      )
    } else {
      candleSeries.current.setMarkers([])
    }

    const closes = candles.map((c) => c.close)
    const { rsi: rsiArr, aladinSignal, aladinFast } = computeAladin(closes, params)
    const toLine = (values: number[]) =>
      candles
        .map((c, i) => ({ time: c.time as Time, value: values[i] }))
        .filter((p) => !Number.isNaN(p.value))

    rsiSeries.current?.setData(toLine(rsiArr))
    signalSeries.current?.setData(toLine(aladinSignal))
    fastSeries.current?.setData(toLine(aladinFast))
    midSeries.current?.setData(candles.map((c) => ({ time: c.time as Time, value: params.midLevel })))

    mainChart.current?.timeScale().fitContent()
    rsiChart.current?.timeScale().fitContent()
  }, [candles, params, levels, showSignals])

  useEffect(() => {
    mainChart.current?.applyOptions({
      timeScale: { secondsVisible: showSeconds },
    })
  }, [showSeconds])

  const lastClose = candles.length ? candles[candles.length - 1].close : null

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex flex-wrap items-center justify-between gap-2">
        <div>
          <span className="font-display font-bold text-sm uppercase tracking-wide text-primary-navy">{symbol}</span>
          <span className="text-xs text-text-faint ml-2">{interval}</span>
          {lastClose != null && (
            <span className="text-sm font-bold tabular-nums ml-3">₹{lastClose.toFixed(2)}</span>
          )}
        </div>
        <span className={`badge ${live ? 'bg-accent-50 text-accent' : 'bg-bg-subtle text-text-faint'}`}>
          {live ? 'LIVE' : 'DEMO'}
        </span>
      </div>
      <div ref={mainRef} />
      <div className="px-5 py-1 border-t border-border bg-bg-subtle/30">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-text-faint">RSI · Aladin</span>
      </div>
      <div ref={rsiRef} />
      <div className="px-5 py-2 border-t border-border flex flex-wrap gap-4 text-[10px] text-text-muted">
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-primary rounded" /> Aladin WMA</span>
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-warn rounded" /> Aladin Fast</span>
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-down rounded" /> SL</span>
        <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-up rounded" /> Target</span>
      </div>
    </div>
  )
}

export function generateDemoCandles(base = 2500, count = 120): ChartCandle[] {
  const out: ChartCandle[] = []
  let price = base
  const now = Math.floor(Date.now() / 1000)
  for (let i = 0; i < count; i++) {
    const o = price
    const c = o + (Math.random() - 0.5) * (base * 0.008)
    out.push({
      time: now - (count - i) * 300,
      open: o,
      high: Math.max(o, c) + Math.random() * (base * 0.002),
      low: Math.min(o, c) - Math.random() * (base * 0.002),
      close: c,
    })
    price = c
  }
  return out
}

const BASE_PRICES: Record<string, number> = {
  RELIANCE: 1425, INFY: 1850, SBIN: 820, TCS: 4100, HDFCBANK: 1680, ICICIBANK: 1280,
  NIFTY: 24800, BANKNIFTY: 52000,
}

export function demoCandlesForSymbol(tradingsymbol: string): ChartCandle[] {
  const key = tradingsymbol.replace(/\d.*/, '').replace(/CE|PE|FUT/g, '') || tradingsymbol
  return generateDemoCandles(BASE_PRICES[key] ?? BASE_PRICES[tradingsymbol] ?? 2500)
}
