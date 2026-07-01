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

type InstrumentMode = 'futures' | 'options'

function formatExpiry(d: string) {
  return new Date(d).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function StrategyBuilder({ accounts }: Props) {
  const qc = useQueryClient()
  const [instrumentType, setInstrumentType] = useState<InstrumentMode>('futures')
  const [underlying, setUnderlying] = useState('NIFTY')
  const [symbol, setSymbol] = useState('')
  const [expiry, setExpiry] = useState('')
  const [optionType, setOptionType] = useState<'CE' | 'PE'>('CE')
  const [strikeSymbol, setStrikeSymbol] = useState('')
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY')
  const [qty, setQty] = useState(1)

  const isFutures = instrumentType === 'futures'
  const isOptions = instrumentType === 'options'

  const { data: futureExpiries = [], isLoading: futExpLoading } = useQuery({
    queryKey: ['expiries', underlying, 'FUT'],
    queryFn: () => api.getInstrumentExpiries(underlying, 'FUT'),
    enabled: isFutures,
    staleTime: 5 * 60_000,
    refetchOnMount: 'always',
  })

  const { data: futureContracts = [], isLoading: futContractsLoading } = useQuery({
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

  const { data: optionExpiries = [], isLoading: optExpLoading } = useQuery({
    queryKey: ['expiries', underlying, 'CE,PE'],
    queryFn: () => api.getInstrumentExpiries(underlying, 'CE,PE'),
    enabled: isOptions,
    staleTime: 5 * 60_000,
    refetchOnMount: 'always',
  })

  const { data: strikeContracts = [], isLoading: strikesLoading } = useQuery({
    queryKey: ['strikes', underlying, expiry, optionType],
    queryFn: () => api.getInstrumentStrikes(underlying, expiry, optionType),
    enabled: isOptions && !!expiry,
    staleTime: 5 * 60_000,
    refetchOnMount: 'always',
  })

  const handleInstrumentTypeChange = useCallback(
    (type: InstrumentMode) => {
      setInstrumentType(type)
      setExpiry('')
      setStrikeSymbol('')
      setSymbol('')
      if (type === 'futures') {
        qc.invalidateQueries({ queryKey: ['expiries', underlying, 'FUT'] })
      } else {
        qc.invalidateQueries({ queryKey: ['expiries', underlying, 'CE,PE'] })
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
    },
    [qc],
  )

  useEffect(() => {
    if (!isFutures || futExpLoading) return
    if (futureExpiries.length > 0 && !expiry) {
      setExpiry(futureExpiries[0])
    }
  }, [isFutures, futureExpiries, expiry, futExpLoading])

  useEffect(() => {
    if (!isOptions || optExpLoading) return
    if (optionExpiries.length > 0 && !expiry) {
      setExpiry(optionExpiries[0])
    }
  }, [isOptions, optionExpiries, expiry, optExpLoading])

  useEffect(() => {
    if (!isFutures || futContractsLoading) return
    if (futureContracts.length === 0) return
    const valid = futureContracts.some((c) => c.tradingsymbol === symbol)
    if (!valid) {
      setSymbol(futureContracts[0].tradingsymbol)
    }
  }, [isFutures, futureContracts, symbol, futContractsLoading])

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

  const selectedInstrument: InstrumentMaster | undefined = useMemo(() => {
    if (isFutures) return futureContracts.find((i) => i.tradingsymbol === symbol)
    if (isOptions) return strikeContracts.find((i) => i.tradingsymbol === strikeSymbol)
    return undefined
  }, [isFutures, isOptions, futureContracts, strikeContracts, symbol, strikeSymbol])

  const finalSymbol = isOptions ? strikeSymbol : symbol
  const lotSize = selectedInstrument?.lot_size ?? 1

  const create = useMutation({
    mutationFn: () =>
      api.createStrategy({
        name: `${INDEX_LABELS[underlying] ?? underlying} ${finalSymbol}`,
        symbol: finalSymbol,
        instrument_type: instrumentType,
        paper_mode: true,
        broker_account_ids: accounts.map((a) => a.id),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategies'] }),
  })

  return (
    <SectionCard title="Strategy Builder" description="Index F&O only — Nifty, Bank Nifty, and other index derivatives">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-3 sm:gap-4">
        <Field label="Instrument">
          <select
            value={instrumentType}
            onChange={(e) => handleInstrumentTypeChange(e.target.value as InstrumentMode)}
            className="input-field"
          >
            <option value="futures">Futures (NFO)</option>
            <option value="options">Options (NFO)</option>
          </select>
        </Field>

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
        <span className="badge bg-warn/10 text-warn">Paper Mode</span>
        <span className="badge bg-bg-subtle text-text-muted">Aladin · 5m / 15m</span>
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
