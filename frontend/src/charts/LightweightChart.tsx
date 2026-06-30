import { useEffect, useRef } from 'react'
import { createChart, type IChartApi, type ISeriesApi } from 'lightweight-charts'

interface Candle {
  time: string
  open: number
  high: number
  low: number
  close: number
}

interface Props {
  candles?: Candle[]
  symbol?: string
}

export function LightweightChart({ candles = [], symbol = 'RELIANCE' }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 420,
      layout: { background: { color: '#FFFFFF' }, textColor: '#64748B' },
      grid: { vertLines: { color: '#E8ECF1' }, horzLines: { color: '#E8ECF1' } },
    })

    const series = chart.addCandlestickSeries({
      upColor: '#16A34A',
      downColor: '#DC2626',
      borderVisible: false,
      wickUpColor: '#16A34A',
      wickDownColor: '#DC2626',
    })

    chartRef.current = chart
    seriesRef.current = series

    const onResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth })
    }
    window.addEventListener('resize', onResize)

    return () => {
      window.removeEventListener('resize', onResize)
      chart.remove()
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current || candles.length === 0) return
    const data = candles.map((c, i) => ({
      time: (Date.now() / 1000 - (candles.length - i) * 300) as unknown as string,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }))
    seriesRef.current.setData(data as never)
    chartRef.current?.timeScale().fitContent()
  }, [candles])

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between">
        <div>
          <span className="font-display font-bold text-sm uppercase tracking-wide text-primary-navy">{symbol}</span>
          <span className="text-xs text-text-faint ml-2">Hilega Milega · 5m</span>
        </div>
        <span className="badge bg-bg-subtle text-text-faint">DEMO DATA</span>
      </div>
      <div ref={containerRef} />
    </div>
  )
}

function generateDemoCandles(base = 2500): Candle[] {
  const out: Candle[] = []
  let price = base
  for (let i = 0; i < 80; i++) {
    const o = price
    const c = o + (Math.random() - 0.5) * 20
    out.push({
      time: String(i),
      open: o,
      high: Math.max(o, c) + Math.random() * 5,
      low: Math.min(o, c) - Math.random() * 5,
      close: c,
    })
    price = c
  }
  return out
}

const BASE_PRICES: Record<string, number> = {
  RELIANCE: 1425,
  INFY: 1850,
  SBIN: 820,
  TCS: 4100,
  HDFCBANK: 1680,
  ICICIBANK: 1280,
}

export function DemoChart({ symbol = 'RELIANCE' }: { symbol?: string }) {
  return <LightweightChart candles={generateDemoCandles(BASE_PRICES[symbol] ?? 2500)} symbol={symbol} />
}
