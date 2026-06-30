import { useCallback, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type InstrumentMaster } from '../api/client'
import { INDEX_LABELS } from './layout/Sidebar'
import { SectionCard } from './ui/PageHeader'

interface Props {
  accounts: { id: string; label: string }[]
}

const INDEX_UNDERLYINGS = [
  { id: 'NIFTY', label: 'Nifty 50' },
  { id: 'BANKNIFTY', label: 'Bank Nifty' },
  { id: 'FINNIFTY', label: 'Fin Nifty' },
  { id: 'MIDCPNIFTY', label: 'Midcap Nifty' },
  { id: 'NIFTYNXT50', label: 'Nifty Next 50' },
]

const FALLBACK_SYMBOLS = ['RELIANCE', 'INFY', 'SBIN', 'TCS', 'HDFCBANK', 'ICICIBANK']

type InstrumentMode = 'equity_intraday' | 'futures' | 'options'

function formatExpiry(d: string) {
  return new Date(d).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function StrategyBuilder({ accounts }: Props) {
  const qc = useQueryClient()
  const [instrumentType, setInstrumentType] = useState<InstrumentMode>('equity_intraday')
  const [underlying, setUnderlying] = useState('NIFTY')
  const [symbolSearch, setSymbolSearch] = useState('')
  const [symbol, setSymbol] = useState('RELIANCE')
  const [expiry, setExpiry] = useState('')
  const [optionType, setOptionType] = useState<'CE' | 'PE'>('CE')
  const [strikeSymbol, setStrikeSymbol] = useState('')
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY')
  const [qty, setQty] = useState(1)

  const isEquity = instrumentType === 'equity_intraday'
  const isFutures = instrumentType === 'futures'
  const isOptions = instrumentType === 'options'

  const {
    data: equityInstruments = [],
    isLoading: equityLoading,
    isFetching: equityFetching,
  } = useQuery({
    queryKey: ['equity-instruments', symbolSearch],
    queryFn: () =>
      api.searchInstruments({
        exchange: 'NSE',
        instrument_type: 'EQ',
        q: symbolSearch || undefined,
        limit: 200,
      }),
    staleTime: 5 * 60_000,
    refetchOnMount: 'always',
  })

  const {
    data: futureExpiries = [],
    isLoading: futExpLoading,
  } = useQuery({
    queryKey: ['expiries', underlying, 'FUT'],
    queryFn: () => api.getInstrumentExpiries(underlying, 'FUT'),
    enabled: isFutures,
    staleTime: 5 * 60_000,
    refetchOnMount: 'always',
  })

  const {
    data: futureContracts = [],
    isLoading: futContractsLoading,
  } = useQuery({
    queryKey: ['futures', underlying, expiry],
    queryFn: () =>
      api.searchInstruments({
        exchange: 'NFO',
        instrument_type: 'FUT',
        underlying,
        expiry,
        limit: 20,
      }),
    enabled: isFutures && !!expiry,
    staleTime: 5 * 60_000,
    refetchOnMount: 'always',
  })

  const {
    data: optionExpiries = [],
    isLoading: optExpLoading,
  } = useQuery({
    queryKey: ['expiries', underlying, 'CE,PE'],
    queryFn: () => api.getInstrumentExpiries(underlying, 'CE,PE'),
    enabled: isOptions,
    staleTime: 5 * 60_000,
    refetchOnMount: 'always',
  })

  const {
    data: strikeContracts = [],
    isLoading: strikesLoading,
  } = useQuery({
    queryKey: ['strikes', underlying, expiry, optionType],
    queryFn: () => api.getInstrumentStrikes(underlying, expiry, optionType),
    enabled: isOptions && !!expiry,
    staleTime: 5 * 60_000,
    refetchOnMount: 'always',
  })

  const equitySymbols = useMemo(() => {
    if (equityInstruments.length > 0) return equityInstruments.map((i) => i.tradingsymbol)
    return FALLBACK_SYMBOLS
  }, [equityInstruments])

  const handleInstrumentTypeChange = useCallback(
    (type: InstrumentMode) => {
      setInstrumentType(type)
      setExpiry('')
      setStrikeSymbol('')
      setSymbolSearch('')
      if (type === 'equity_intraday') {
        setSymbol(FALLBACK_SYMBOLS[0])
        qc.invalidateQueries({ queryKey: ['equity-instruments'] })
      } else {
        setSymbol('')
        if (type === 'futures') {
          qc.invalidateQueries({ queryKey: ['expiries', underlying, 'FUT'] })
        } else {
          qc.invalidateQueries({ queryKey: ['expiries', underlying, 'CE,PE'] })
        }
      }
    },
    [qc, underlying],
  )

  const handleUnderlyingChange = useCallback(
    (value: string) => {
      setUnderlying(value)
      setExpiry('')
      setStrikeSymbol('')
      setSymbol('')
      qc.invalidateQueries({ queryKey: ['expiries', value] })
      qc.invalidateQueries({ queryKey: ['futures', value] })
      qc.invalidateQueries({ queryKey: ['strikes', value] })
    },
    [qc],
  )

  // Sync equity symbol when list loads or type switches to equity
  useEffect(() => {
    if (!isEquity) return
    if (equitySymbols.length === 0) return
    if (!equitySymbols.includes(symbol)) {
      setSymbol(equitySymbols[0])
    }
  }, [isEquity, equitySymbols, symbol])

  // Futures: pick first expiry when none selected
  useEffect(() => {
    if (!isFutures || futExpLoading) return
    if (futureExpiries.length > 0 && !expiry) {
      setExpiry(futureExpiries[0])
    }
  }, [isFutures, futureExpiries, expiry, futExpLoading])

  // Options: pick first expiry when none selected
  useEffect(() => {
    if (!isOptions || optExpLoading) return
    if (optionExpiries.length > 0 && !expiry) {
      setExpiry(optionExpiries[0])
    }
  }, [isOptions, optionExpiries, expiry, optExpLoading])

  // Futures: pick contract when contracts load
  useEffect(() => {
    if (!isFutures || futContractsLoading) return
    if (futureContracts.length === 0) return
    const valid = futureContracts.some((c) => c.tradingsymbol === symbol)
    if (!valid) {
      setSymbol(futureContracts[0].tradingsymbol)
    }
  }, [isFutures, futureContracts, symbol, futContractsLoading])

  // Options: pick strike when chain loads
  useEffect(() => {
    if (!isOptions || strikesLoading) return
    if (strikeContracts.length === 0) {
      setStrikeSymbol('')
      return
    }
    const valid = strikeContracts.some((c) => c.tradingsymbol === strikeSymbol)
    if (!valid) {
      setStrikeSymbol(strikeContracts[0].tradingsymbol)
    }
  }, [isOptions, strikeContracts, strikeSymbol, strikesLoading])

  useEffect(() => {
    if (isOptions) setOptionType(side === 'BUY' ? 'CE' : 'PE')
  }, [side, isOptions])

  const equitySelectValue = equitySymbols.includes(symbol) ? symbol : equitySymbols[0] ?? ''

  const selectedInstrument: InstrumentMaster | undefined = useMemo(() => {
    if (isEquity) return equityInstruments.find((i) => i.tradingsymbol === equitySelectValue)
    if (isFutures) return futureContracts.find((i) => i.tradingsymbol === symbol)
    if (isOptions) return strikeContracts.find((i) => i.tradingsymbol === strikeSymbol)
    return undefined
  }, [isEquity, isFutures, isOptions, equityInstruments, futureContracts, strikeContracts, equitySelectValue, symbol, strikeSymbol])

  const finalSymbol = isOptions ? strikeSymbol : isEquity ? equitySelectValue : symbol
  const lotSize = selectedInstrument?.lot_size ?? 1

  const create = useMutation({
    mutationFn: () =>
      api.createStrategy({
        name: isEquity
          ? `${finalSymbol} ${instrumentType}`
          : `${INDEX_LABELS[underlying] ?? underlying} ${finalSymbol}`,
        symbol: finalSymbol,
        instrument_type: instrumentType,
        paper_mode: true,
        broker_account_ids: accounts.map((a) => a.id),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategies'] }),
  })

  const equityBusy = equityLoading || equityFetching

  return (
    <SectionCard title="Strategy Builder" description="Symbols from daily Zerodha instrument master">
      <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-4">
        <Field label="Instrument">
          <select
            value={instrumentType}
            onChange={(e) => handleInstrumentTypeChange(e.target.value as InstrumentMode)}
            className="input-field"
          >
            <option value="equity_intraday">Equity Intraday (NSE)</option>
            <option value="futures">Futures (NFO)</option>
            <option value="options">Options (NFO)</option>
          </select>
        </Field>

        {(isFutures || isOptions) && (
          <Field label="Underlying">
            <select
              value={underlying}
              onChange={(e) => handleUnderlyingChange(e.target.value)}
              className="input-field"
            >
              {INDEX_UNDERLYINGS.map((u) => (
                <option key={u.id} value={u.id}>{u.label}</option>
              ))}
            </select>
          </Field>
        )}

        {isEquity && (
          <Field label="Search Symbol" className="lg:col-span-2">
            <input
              type="text"
              placeholder="Type to filter…"
              value={symbolSearch}
              onChange={(e) => setSymbolSearch(e.target.value)}
              className="input-field mb-2"
            />
            <select
              value={equitySelectValue}
              onChange={(e) => setSymbol(e.target.value)}
              className="input-field"
              disabled={equityBusy && equityInstruments.length === 0}
            >
              {equityBusy && equityInstruments.length === 0 ? (
                <option value="">Loading symbols…</option>
              ) : (
                equitySymbols.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))
              )}
            </select>
          </Field>
        )}

        {isFutures && (
          <>
            <Field label="Expiry">
              <select
                value={expiry}
                onChange={(e) => setExpiry(e.target.value)}
                className="input-field"
                disabled={futExpLoading}
              >
                {futExpLoading ? (
                  <option value="">Loading…</option>
                ) : futureExpiries.length === 0 ? (
                  <option value="">No expiries</option>
                ) : (
                  futureExpiries.map((d) => (
                    <option key={d} value={d}>{formatExpiry(d)}</option>
                  ))
                )}
              </select>
            </Field>
            <Field label="Contract">
              <select
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="input-field"
                disabled={!expiry || futContractsLoading}
              >
                {futContractsLoading ? (
                  <option value="">Loading…</option>
                ) : futureContracts.length === 0 ? (
                  <option value="">No contracts</option>
                ) : (
                  futureContracts.map((c) => (
                    <option key={c.tradingsymbol} value={c.tradingsymbol}>{c.tradingsymbol}</option>
                  ))
                )}
              </select>
            </Field>
          </>
        )}

        {isOptions && (
          <>
            <Field label="Expiry">
              <select
                value={expiry}
                onChange={(e) => {
                  setExpiry(e.target.value)
                  setStrikeSymbol('')
                }}
                className="input-field"
                disabled={optExpLoading}
              >
                {optExpLoading ? (
                  <option value="">Loading…</option>
                ) : optionExpiries.length === 0 ? (
                  <option value="">No expiries</option>
                ) : (
                  optionExpiries.map((d) => (
                    <option key={d} value={d}>{formatExpiry(d)}</option>
                  ))
                )}
              </select>
            </Field>
            <Field label="Option Type">
              <select
                value={optionType}
                onChange={(e) => {
                  setOptionType(e.target.value as 'CE' | 'PE')
                  setStrikeSymbol('')
                }}
                className="input-field"
              >
                <option value="CE">Call (CE)</option>
                <option value="PE">Put (PE)</option>
              </select>
            </Field>
            <Field label="Strike Price" className="lg:col-span-2">
              <select
                value={strikeSymbol}
                onChange={(e) => setStrikeSymbol(e.target.value)}
                className="input-field"
                disabled={!expiry || strikesLoading}
              >
                {strikesLoading ? (
                  <option value="">Loading strikes…</option>
                ) : strikeContracts.length === 0 ? (
                  <option value="">No strikes — pick expiry</option>
                ) : (
                  strikeContracts.map((c) => (
                    <option key={c.tradingsymbol} value={c.tradingsymbol}>
                      {c.strike != null ? `₹${c.strike.toLocaleString('en-IN')} · ${c.tradingsymbol}` : c.tradingsymbol}
                    </option>
                  ))
                )}
              </select>
            </Field>
          </>
        )}

        <Field label="Side">
          <div className="flex rounded-btn border border-border overflow-hidden h-[42px]">
            {(['BUY', 'SELL'] as const).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSide(s)}
                className={`flex-1 text-sm font-semibold transition-colors ${
                  side === s
                    ? s === 'BUY' ? 'bg-up text-white' : 'bg-down text-white'
                    : 'bg-surface text-text-muted hover:bg-bg-subtle'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </Field>

        <Field label="Quantity">
          <div className="flex items-center border border-border rounded-btn h-[42px] bg-surface">
            <button type="button" onClick={() => setQty(Math.max(lotSize, qty - lotSize))} className="px-3 text-text-faint hover:text-text">−</button>
            <span className="flex-1 text-center font-semibold tabular-nums">{qty}</span>
            <button type="button" onClick={() => setQty(qty + lotSize)} className="px-3 text-text-faint hover:text-text">+</button>
          </div>
        </Field>
      </div>

      <div className="flex flex-wrap gap-2 mt-4">
        <span className="badge bg-bg-subtle text-text-muted">Lot: {lotSize}</span>
        {finalSymbol && (
          <span className="badge bg-primary-50 text-primary font-mono text-[10px]">{finalSymbol}</span>
        )}
        {selectedInstrument?.name && (
          <span className="badge bg-bg-subtle text-text-muted truncate max-w-[180px]">{selectedInstrument.name}</span>
        )}
        <span className="badge bg-warn/10 text-warn">Paper Mode</span>
        <span className="badge bg-bg-subtle text-text-muted">5m / 15m TF</span>
      </div>

      <button
        onClick={() => create.mutate()}
        disabled={create.isPending || accounts.length === 0 || !finalSymbol || (isOptions && !strikeSymbol)}
        className="btn-accent w-full mt-5 py-3 text-base"
      >
        {create.isPending ? 'Creating…' : 'ADD STRATEGY'}
      </button>
      {accounts.length === 0 && (
        <p className="text-xs text-warn mt-2 text-center">Link a broker account first → Accounts</p>
      )}
      {isEquity && !equityBusy && equityInstruments.length === 0 && (
        <p className="text-xs text-text-faint mt-2 text-center">
          No equity symbols in DB — run instrument sync in Settings
        </p>
      )}
      {isOptions && !strikesLoading && strikeContracts.length === 0 && expiry && (
        <p className="text-xs text-text-faint mt-2 text-center">
          No strikes for {INDEX_LABELS[underlying] ?? underlying} — run instrument sync in Settings
        </p>
      )}
      {create.isSuccess && (
        <p className="text-xs text-up mt-2 text-center">Strategy created — start it in the list below</p>
      )}
    </SectionCard>
  )
}

function Field({
  label,
  children,
  className = '',
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={className}>
      <label className="text-[11px] font-semibold uppercase tracking-wider text-text-faint block mb-1.5">{label}</label>
      {children}
    </div>
  )
}
