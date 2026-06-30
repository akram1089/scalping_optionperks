import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type InstrumentMaster } from '../../api/client'

export interface ChartSymbol {
  tradingsymbol: string
  instrument_token: number
  exchange: string
  segment: 'equity' | 'futures' | 'options'
  label: string
}

type Segment = 'equity' | 'futures' | 'options'

const INDEX_UNDERLYINGS = [
  { id: 'NIFTY', label: 'Nifty 50' },
  { id: 'BANKNIFTY', label: 'Bank Nifty' },
  { id: 'FINNIFTY', label: 'Fin Nifty' },
  { id: 'MIDCPNIFTY', label: 'Midcap Nifty' },
  { id: 'RELIANCE', label: 'Reliance' },
]

const FALLBACK_EQUITY = ['RELIANCE', 'INFY', 'SBIN', 'TCS', 'HDFCBANK', 'ICICIBANK']

function formatExpiry(d: string) {
  return new Date(d).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

function toChartSymbol(inst: InstrumentMaster, segment: Segment): ChartSymbol {
  return {
    tradingsymbol: inst.tradingsymbol,
    instrument_token: inst.instrument_token,
    exchange: inst.exchange,
    segment,
    label: inst.tradingsymbol,
  }
}

interface Props {
  value: ChartSymbol | null
  onChange: (sym: ChartSymbol) => void
}

export function ChartSymbolPicker({ value, onChange }: Props) {
  const [segment, setSegment] = useState<Segment>('equity')
  const [equitySearch, setEquitySearch] = useState('')
  const [underlying, setUnderlying] = useState('NIFTY')
  const [expiry, setExpiry] = useState('')
  const [optionType, setOptionType] = useState<'CE' | 'PE'>('CE')

  const { data: equityList = [] } = useQuery({
    queryKey: ['chart-equity', equitySearch],
    queryFn: () =>
      api.searchInstruments({ exchange: 'NSE', instrument_type: 'EQ', q: equitySearch || undefined, limit: 150 }),
    enabled: segment === 'equity',
    staleTime: 60_000,
  })

  const { data: futExpiries = [] } = useQuery({
    queryKey: ['chart-fut-exp', underlying],
    queryFn: () => api.getInstrumentExpiries(underlying, 'FUT'),
    enabled: segment === 'futures',
    staleTime: 60_000,
  })

  const { data: futContracts = [] } = useQuery({
    queryKey: ['chart-fut', underlying, expiry],
    queryFn: () =>
      api.searchInstruments({ exchange: 'NFO', instrument_type: 'FUT', underlying, expiry, limit: 20 }),
    enabled: segment === 'futures' && !!expiry,
    staleTime: 60_000,
  })

  const { data: optExpiries = [] } = useQuery({
    queryKey: ['chart-opt-exp', underlying],
    queryFn: () => api.getInstrumentExpiries(underlying, 'CE,PE'),
    enabled: segment === 'options',
    staleTime: 60_000,
  })

  const { data: strikeContracts = [] } = useQuery({
    queryKey: ['chart-strikes', underlying, expiry, optionType],
    queryFn: () => api.getInstrumentStrikes(underlying, expiry, optionType),
    enabled: segment === 'options' && !!expiry,
    staleTime: 60_000,
  })

  const equityOptions = useMemo(() => {
    if (equityList.length) return equityList
    return FALLBACK_EQUITY.map((s) => ({
      instrument_token: 0,
      exchange: 'NSE',
      tradingsymbol: s,
      name: s,
      lot_size: 1,
      instrument_type: 'EQ',
      segment: 'NSE',
      expiry: null,
      strike: null,
      tick_size: 0.05,
      is_active: true,
    })) as InstrumentMaster[]
  }, [equityList])

  useEffect(() => {
    setExpiry('')
  }, [segment, underlying])

  useEffect(() => {
    if (segment === 'futures' && futExpiries.length && !expiry) {
      setExpiry(futExpiries[0])
    }
    if (segment === 'options' && optExpiries.length && !expiry) {
      setExpiry(optExpiries[0])
    }
  }, [segment, futExpiries, optExpiries, expiry])

  const pickEquity = useCallback(
    (inst: InstrumentMaster) => onChange(toChartSymbol(inst, 'equity')),
    [onChange],
  )

  return (
    <div className="card p-4 space-y-4">
      <div className="flex flex-wrap gap-2">
        {(['equity', 'futures', 'options'] as Segment[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setSegment(s)}
            className={`px-4 py-2 rounded-pill text-sm font-semibold capitalize transition-colors ${
              segment === s ? 'bg-primary-navy text-white' : 'bg-bg-subtle text-text-muted hover:text-text'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {segment === 'equity' && (
        <div className="space-y-2">
          <input
            placeholder="Search equity symbol…"
            value={equitySearch}
            onChange={(e) => setEquitySearch(e.target.value)}
            className="input-field"
          />
          <div className="max-h-40 overflow-y-auto grid grid-cols-2 sm:grid-cols-3 gap-1">
            {equityOptions.map((inst) => (
              <button
                key={inst.tradingsymbol}
                type="button"
                onClick={() => pickEquity(inst)}
                className={`text-left px-2 py-1.5 rounded-btn text-xs font-medium truncate ${
                  value?.tradingsymbol === inst.tradingsymbol
                    ? 'bg-accent-50 text-accent border border-accent/30'
                    : 'hover:bg-bg-subtle'
                }`}
              >
                {inst.tradingsymbol}
              </button>
            ))}
          </div>
        </div>
      )}

      {(segment === 'futures' || segment === 'options') && (
        <div className="grid sm:grid-cols-2 gap-3">
          <select value={underlying} onChange={(e) => setUnderlying(e.target.value)} className="input-field">
            {INDEX_UNDERLYINGS.map((u) => (
              <option key={u.id} value={u.id}>{u.label}</option>
            ))}
          </select>
          <select value={expiry} onChange={(e) => setExpiry(e.target.value)} className="input-field">
            <option value="">Select expiry</option>
            {(segment === 'futures' ? futExpiries : optExpiries).map((d) => (
              <option key={d} value={d}>{formatExpiry(d)}</option>
            ))}
          </select>
        </div>
      )}

      {segment === 'futures' && expiry && (
        <div className="flex flex-wrap gap-2">
          {futContracts.map((inst) => (
            <button
              key={inst.tradingsymbol}
              type="button"
              onClick={() => onChange(toChartSymbol(inst, 'futures'))}
              className={`px-3 py-1.5 rounded-btn text-xs font-medium ${
                value?.tradingsymbol === inst.tradingsymbol ? 'bg-accent-50 text-accent' : 'bg-bg-subtle hover:bg-border'
              }`}
            >
              {inst.tradingsymbol}
            </button>
          ))}
          {!futContracts.length && <p className="text-xs text-text-muted">No futures for this expiry</p>}
        </div>
      )}

      {segment === 'options' && expiry && (
        <>
          <div className="flex gap-2">
            {(['CE', 'PE'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setOptionType(t)}
                className={`px-4 py-1.5 rounded-pill text-xs font-bold ${
                  optionType === t ? (t === 'CE' ? 'bg-up text-white' : 'bg-down text-white') : 'bg-bg-subtle'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
          <div className="max-h-48 overflow-y-auto grid grid-cols-3 sm:grid-cols-4 gap-1">
            {strikeContracts.map((inst) => (
              <button
                key={inst.tradingsymbol}
                type="button"
                onClick={() => onChange(toChartSymbol(inst, 'options'))}
                className={`px-2 py-1.5 rounded-btn text-xs tabular-nums ${
                  value?.tradingsymbol === inst.tradingsymbol
                    ? 'bg-accent-50 text-accent font-semibold'
                    : 'hover:bg-bg-subtle'
                }`}
              >
                {inst.strike?.toLocaleString('en-IN')}
              </button>
            ))}
          </div>
        </>
      )}

      {value && (
        <p className="text-xs text-text-muted border-t border-border pt-3">
          Selected: <strong className="text-text">{value.tradingsymbol}</strong>
          {value.instrument_token ? ` · token ${value.instrument_token}` : ' · demo (no token)'}
        </p>
      )}
    </div>
  )
}
