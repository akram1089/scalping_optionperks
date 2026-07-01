import { create } from 'zustand'
import { api, type StreamStatus, type TickData } from '../api/client'

interface AuthState {
  email: string | null
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string) => Promise<void>
  logout: () => void
  hydrate: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  email: null,
  isAuthenticated: !!localStorage.getItem('access_token'),
  login: async (email, password) => {
    const tokens = await api.login(email, password)
    localStorage.setItem('access_token', tokens.access_token)
    localStorage.setItem('refresh_token', tokens.refresh_token)
    set({ email, isAuthenticated: true })
  },
  signup: async (email, password) => {
    const tokens = await api.signup(email, password)
    localStorage.setItem('access_token', tokens.access_token)
    localStorage.setItem('refresh_token', tokens.refresh_token)
    set({ email, isAuthenticated: true })
  },
  logout: () => {
    localStorage.clear()
    set({ email: null, isAuthenticated: false })
  },
  hydrate: async () => {
    if (!localStorage.getItem('access_token')) return
    try {
      const me = await api.me()
      const kill = await api.getKillSwitch()
      set({ email: me.email, isAuthenticated: true })
      useLiveStore.getState().setKillSwitch(kill.kill_switch)
    } catch {
      localStorage.clear()
      set({ email: null, isAuthenticated: false })
    }
  },
}))

interface LiveState {
  ticks: Record<string, TickData>
  selectedAccountId: string | null
  killSwitch: boolean
  wsConnected: boolean
  streamStatus: StreamStatus | null
  setTick: (data: TickData) => void
  setSelectedAccount: (id: string | null) => void
  setKillSwitch: (v: boolean) => void
  setWsConnected: (v: boolean) => void
  setStreamStatus: (s: StreamStatus | null) => void
}

export const useLiveStore = create<LiveState>((set) => ({
  ticks: {},
  selectedAccountId: null,
  killSwitch: false,
  wsConnected: false,
  streamStatus: null,
  setTick: (data) =>
    set((s) => ({ ticks: { ...s.ticks, [data.symbol]: { ...s.ticks[data.symbol], ...data } } })),
  setSelectedAccount: (id) => set({ selectedAccountId: id }),
  setKillSwitch: (v) => set({ killSwitch: v }),
  setWsConnected: (v) => set({ wsConnected: v }),
  setStreamStatus: (streamStatus) => set({ streamStatus }),
}))

interface UiState {
  sidebarCollapsed: boolean
  sidebarOpen: boolean
  toggleSidebar: () => void
  setSidebarCollapsed: (v: boolean) => void
  setSidebarOpen: (v: boolean) => void
}

const SIDEBAR_KEY = 'scalpdesk_sidebar_collapsed'

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: localStorage.getItem(SIDEBAR_KEY) === 'true',
  sidebarOpen: false,
  toggleSidebar: () =>
    set((s) => {
      const next = !s.sidebarCollapsed
      localStorage.setItem(SIDEBAR_KEY, String(next))
      return { sidebarCollapsed: next }
    }),
  setSidebarCollapsed: (v) => {
    localStorage.setItem(SIDEBAR_KEY, String(v))
    set({ sidebarCollapsed: v })
  },
  setSidebarOpen: (v) => set({ sidebarOpen: v }),
}))
