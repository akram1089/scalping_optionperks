import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { TradingChart, demoCandlesForSymbol, type ChartCandle } from '../charts/TradingChart'
import { DEFAULT_INDICATOR_PARAMS, type IndicatorParams } from '../charts/indicators'
import { ChartSymbolPicker, type ChartSymbol } from '../components/charts/ChartSymbolPicker'
import { PageHeader, SectionCard } from '../components/ui/PageHeader'

const INTERVALS = [
  { value: 'minute', label: '1m' },
  { value: '3minute', label: '3m' },
  { value: '5minute', label: '5m' },
  { value: '15minute', label: '15m' },
  { value: '30minute', label: '30m' },
  { value: '60minute', label: '1h' },
  { value: 'day', label: '1D' },
]

const DEFAULT_SYMBOL: ChartSymbol = {
  tradingsymbol: 'RELIANCE',
  instrument_token: 0,
  exchange: 'NSE',
  segment: 'equity',
  label: 'RELIANCE',
}

export function ChartsPage() {
  const [symbol, setSymbol] = useState<ChartSymbol>(DEFAULT_SYMBOL)
  const [interval, setInterval] = useState('5minute')
  const [params, setParams] = useState<IndicatorParams>({ ...DEFAULT_INDICATOR_PARAMS })
  const [entry, setEntry] = useState<string>('')
  const [stopLoss, setStopLoss] = useState<string>('')
  const [target, setTarget] = useState<string>('')
  const [showSignals, setShowSignals] = useState(true)
  const [rrRatio, setRrRatio] = useState(2)

  const { data: accounts = [] } = useQuery({ queryKey: ['accounts'], queryFn: api.getAccounts })
  const connectedAccount = accounts.find((a) => a.session_active)

  const canFetchLive = Boolean(symbol.instrument_token && connectedAccount)

  const { data: liveData, isLoading, error } = useQuery({
    queryKey: ['chart-candles', symbol.tradingsymbol, symbol.instrument_token, interval, connectedAccount?.id],
    queryFn: () =>
      api.getChartCandles({
        instrument_token: symbol.instrument_token,
        tradingsymbol: symbol.tradingsymbol,
        exchange: symbol.exchange,
        interval,
        days: interval === 'day' ? 120 : 5,
        account_id: connectedAccount?.id,
      }),
    enabled: canFetchLive,
    staleTime: 30_000,
    retry: 1,
  })

  const candles: ChartCandle[] = useMemo(() => {
    if (liveData?.candles?.length) return liveData.candles
    return demoCandlesForSymbol(symbol.tradingsymbol)
  }, [liveData, symbol.tradingsymbol])

  const isLive = Boolean(liveData?.live && liveData.candles.length)

  const lastClose = candles.length ? candles[candles.length - 1].close : 0

  useEffect(() => {
    setEntry('')
    setStopLoss('')
    setTarget('')
  }, [symbol.tradingsymbol, symbol.instrument_token])

  useEffect(() => {
    if (!entry && lastClose) {
      setEntry(lastClose.toFixed(2))
    }
  }, [lastClose, symbol.tradingsymbol, entry])

  const applyRiskFromEntry = (side: 'long' | 'short' = 'long') => {
    const e = parseFloat(entry) || lastClose
    const riskPct = 0.005
    const risk = e * riskPct
    if (side === 'long') {
      setStopLoss((e - risk).toFixed(2))
      setTarget((e + risk * rrRatio).toFixed(2))
    } else {
      setStopLoss((e + risk).toFixed(2))
      setTarget((e - risk * rrRatio).toFixed(2))
    }
    setEntry(e.toFixed(2))
  }

  const levels = {
    entry: entry ? parseFloat(entry) : undefined,
    stopLoss: stopLoss ? parseFloat(stopLoss) : undefined,
    target: target ? parseFloat(target) : undefined,
  }

  const intervalLabel = INTERVALS.find((i) => i.value === interval)?.label ?? interval

  return (
    <div className="p-6 lg:p-8 max-w-[1600px]">
      <PageHeader
        title="Charts"
        subtitle="Live candles · Hilega Milega indicator · SL & target overlays"
        action={
          <select value={interval} onChange={(e) => setInterval(e.target.value)} className="input-field w-auto">
            {INTERVALS.map((i) => (
              <option key={i.value} value={i.value}>{i.label}</option>
            ))}
          </select>
        }
      />

      {!connectedAccount && (
        <div className="mb-4 p-3 rounded-btn bg-warn/10 text-warn text-sm">
          Connect a broker account for live candles. Demo data shown until connected.
        </div>
      )}
      {error && (
        <div className="mb-4 p-3 rounded-btn bg-down/10 text-down text-sm">
          {(error as Error).message} — showing demo data.
        </div>
      )}

      <div className="grid xl:grid-cols-4 gap-6">
        <div className="xl:col-span-3 space-y-4">
          {isLoading && canFetchLive && (
            <p className="text-sm text-text-muted">Loading live candles…</p>
          )}
          <TradingChart
            candles={candles}
            symbol={symbol.tradingsymbol}
            interval={intervalLabel}
            live={isLive}
            params={params}
            levels={levels}
            showSignals={showSignals}
          />
        </div>

        <div className="space-y-4">
          <ChartSymbolPicker value={symbol} onChange={setSymbol} />

          <SectionCard title="Custom Indicator" description="Hilega Milega — edit like TradingView inputs">
            <div className="grid grid-cols-2 gap-3 text-sm">
              {(
                [
                  ['rsiLength', 'RSI Length'],
                  ['wmaLength', 'Hilega WMA'],
                  ['emaLength', 'Milega EMA'],
                  ['midLevel', 'Mid Level'],
                ] as const
              ).map(([key, label]) => (
                <label key={key} className="space-y-1">
                  <span className="text-xs text-text-muted">{label}</span>
                  <input
                    type="number"
                    value={params[key]}
                    onChange={(e) => setParams({ ...params, [key]: +e.target.value })}
                    className="input-field"
                    min={1}
                  />
                </label>
              ))}
            </div>
            <label className="flex items-center gap-2 mt-3 text-sm text-text-muted">
              <input type="checkbox" checked={showSignals} onChange={(e) => setShowSignals(e.target.checked)} />
              Show BUY/SELL markers on chart
            </label>
          </SectionCard>

          <SectionCard title="Trade Levels" description="Visible on chart like Lemonn SL/Target lines">
            <div className="space-y-3 text-sm">
              <label className="block space-y-1">
                <span className="text-xs text-text-muted">Entry</span>
                <input type="number" step="0.05" value={entry} onChange={(e) => setEntry(e.target.value)} className="input-field" />
              </label>
              <label className="block space-y-1">
                <span className="text-xs text-text-muted">Stop Loss</span>
                <input type="number" step="0.05" value={stopLoss} onChange={(e) => setStopLoss(e.target.value)} className="input-field" />
              </label>
              <label className="block space-y-1">
                <span className="text-xs text-text-muted">Target</span>
                <input type="number" step="0.05" value={target} onChange={(e) => setTarget(e.target.value)} className="input-field" />
              </label>
              <label className="block space-y-1">
                <span className="text-xs text-text-muted">R:R Ratio (auto SL/Target)</span>
                <input type="number" step="0.5" min={1} value={rrRatio} onChange={(e) => setRrRatio(+e.target.value)} className="input-field" />
              </label>
              <div className="flex flex-wrap gap-2 pt-1">
                <button type="button" onClick={() => applyRiskFromEntry('long')} className="btn-secondary py-2 text-xs">
                  Long SL/Target
                </button>
                <button type="button" onClick={() => applyRiskFromEntry('short')} className="btn-secondary py-2 text-xs">
                  Short SL/Target
                </button>
                <button
                  type="button"
                  onClick={() => setEntry(lastClose.toFixed(2))}
                  className="btn-secondary py-2 text-xs"
                >
                  Entry = LTP
                </button>
              </div>
            </div>
          </SectionCard>
        </div>
      </div>
    </div>
  )
}
