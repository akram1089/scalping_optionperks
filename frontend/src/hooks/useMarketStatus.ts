import { useEffect, useState } from 'react'

export function useClock() {
  const [time, setTime] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return time
}

export function useMarketStatus() {
  const [status, setStatus] = useState(getMarketStatus())
  useEffect(() => {
    const id = setInterval(() => setStatus(getMarketStatus()), 30000)
    return () => clearInterval(id)
  }, [])
  return status
}

function getMarketStatus(): { open: boolean; label: string } {
  const now = new Date()
  const ist = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }))
  const day = ist.getDay()
  if (day === 0 || day === 6) return { open: false, label: 'MARKET CLOSED' }
  const mins = ist.getHours() * 60 + ist.getMinutes()
  const open = mins >= 9 * 60 + 15 && mins <= 15 * 60 + 30
  return { open, label: open ? 'MARKET OPEN' : 'MARKET CLOSED' }
}

export function formatISTTime(date: Date) {
  return date.toLocaleTimeString('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  })
}
