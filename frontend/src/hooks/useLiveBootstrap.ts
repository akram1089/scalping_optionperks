import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { useLiveStore } from '../store'

/** When a Zerodha account is connected, bootstrap index LTP streaming and select that account. */
export function useLiveBootstrap() {
  const setSelectedAccount = useLiveStore((s) => s.setSelectedAccount)
  const selectedAccountId = useLiveStore((s) => s.selectedAccountId)

  const { data: accounts = [] } = useQuery({
    queryKey: ['accounts'],
    queryFn: api.getAccounts,
    refetchInterval: 60_000,
  })

  useEffect(() => {
    const connectedZerodha = accounts.find((a) => a.broker === 'zerodha' && a.session_active)
    if (!connectedZerodha) return

    if (!selectedAccountId) {
      setSelectedAccount(connectedZerodha.id)
    }

    api.bootstrapLiveTicker().catch(() => {
      /* ticker may already be running */
    })
  }, [accounts, selectedAccountId, setSelectedAccount])
}
