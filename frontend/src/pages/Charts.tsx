import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { TradingChart, demoCandlesForSymbol, type ChartCandle } from '../charts/TradingChart'
import { DEFAULT_INDICATOR_PARAMS, type IndicatorParams } from '../charts/indicators'
import { ChartSymbolPicker, type ChartSymbol } from '../components/charts/ChartSymbolPicker'
import { PageHeader, SectionCard } from '../components/ui/PageHeader'
import { useLiveTickCandles } from '../hooks/useLiveTickCandles'

const INTERVALS = [
  { value: 'tick', label: '1s' },
  { value: 'minute', label: '1m' },
  { value: '3minute', label: '3m' },
  { value: '5minute', label: '5m' },
  { value: '15minute', label: '15m' },
  { value: '30minute', label: '30m' },
  { value: '60minute', label: '1h' },
  { value: 'day', label: '1D' },
]

const DEFAULT_SYMBOL: ChartSymbol = {
  tradingsymbol: 'NIFTY',
  instrument_token: 0,
  exchange: 'NFO',
  segment: 'futures',
  label: 'NIFTY FUT',
}

export function ChartsPage() {
  const [symbol, setSymbol] = useState<ChartSymbol>(DEFAULT_SYMBOL)
  const [interval, setInterval] = useState('tick')
  const [params, setParams] = useState<IndicatorParams>({ ...DEFAULT_INDICATOR_PARAMS })
  const [entry, setEntry] = useState<string>('')
  const [stopLoss, setStopLoss] = useState<string>('')
  const [target, setTarget] = useState<string>('')
  const [showSignals, setShowSignals] = useState(true)
  const [rrRatio, setRrRatio] = useState(2)

  const { data: accounts = [] } = useQuery({ queryKey: ['accounts'], queryFn: api.getAccounts })
  const connectedAccount = accounts.find((a) => a.session_active)

  const { data: defaultFut } = useQuery({
    queryKey: ['chart-default-nifty-fut'],
    queryFn: () => api.searchInstruments({ exchange: 'NFO', instrument_type: 'FUT', underlying: 'NIFTY', limit: 1 }),
    staleTime: 3600_000,
  })

  useEffect(() => {
    const inst = defaultFut?.[0]
    if (inst?.instrument_token && symbol.instrument_token === 0) {
      setSymbol({
        tradingsymbol: inst.tradingsymbol,
        instrument_token: inst.instrument_token,
        exchange: inst.exchange,
        segment: 'futures',
        label: inst.tradingsymbol,
      })
    }
  }, [defaultFut, symbol.instrument_token])

  const isTickInterval = interval === 'tick'
  const canFetchLive = Boolean(symbol.instrument_token && connectedAccount)

  const { data: seedData } = useQuery({
    queryKey: ['chart-seed', symbol.instrument_token, connectedAccount?.id],
    queryFn: () =>
      api.getChartCandles({
        instrument_token: symbol.instrument_token,
        tradingsymbol: symbol.tradingsymbol,
        exchange: symbol.exchange,
        interval: 'minute',
        days: 1,
        account_id: connectedAccount?.id,
      }),
    enabled: canFetchLive && isTickInterval,
    staleTime: 60_000,
  })

  const seedClose = seedData?.candles?.length
    ? seedData.candles[seedData.candles.length - 1].close
    : undefined

  const { candles: tickCandles } = useLiveTickCandles(
    symbol.instrument_token,
    symbol.tradingsymbol,
    Boolean(canFetchLive && isTickInterval),
    seedClose,
  )

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
    enabled: canFetchLive && !isTickInterval,
    staleTime: isTickInterval ? 0 : 30_000,
    refetchInterval: isTickInterval ? false : 30_000,
    retry: 1,
  })

  const candles: ChartCandle[] = useMemo(() => {
    if (isTickInterval) {
      if (tickCandles.length) return tickCandles
      return seedClose ? [] : demoCandlesForSymbol(symbol.tradingsymbol)
    }
    if (liveData?.candles?.length) return liveData.candles
    return demoCandlesForSymbol(symbol.tradingsymbol)
  }, [isTickInterval, tickCandles, liveData, symbol.tradingsymbol, seedClose])

  const isLive = isTickInterval
    ? Boolean(canFetchLive && tickCandles.length > 0)
    : Boolean(liveData?.live && liveData.candles.length)

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
    <div className="px-4 py-4 sm:p-6 lg:p-8 max-w-[1600px]">
      <PageHeader
        title="Charts"
        subtitle="Live candles · Aladin indicator · SL & target overlays"
        action={
          <select value={interval} onChange={(e) => setInterval(e.target.value)} className="input-field w-full sm:w-auto">
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
          {isTickInterval && canFetchLive && tickCandles.length === 0 && (
            <p className="text-sm text-text-muted">Waiting for live ticks on 1s chart…</p>
          )}
          {isLoading && canFetchLive && !isTickInterval && (
            <p className="text-sm text-text-muted">Loading live candles…</p>
          )}
          <TradingChart
            candles={candles}
            symbol={symbol.tradingsymbol}
            interval={intervalLabel}
            live={isLive}
            showSeconds={isTickInterval}
            params={params}
            levels={levels}
            showSignals={showSignals}
          />
        </div>

        <div className="space-y-4">
          <ChartSymbolPicker value={symbol} onChange={setSymbol} />

          <SectionCard title="Custom Indicator" description="Aladin — edit like TradingView inputs">
            <div className="grid grid-cols-2 gap-3 text-sm">
              {(
                [
                  ['rsiLength', 'RSI Length'],
                  ['wmaLength', 'Aladin WMA'],
                  ['emaLength', 'Aladin Fast'],
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
