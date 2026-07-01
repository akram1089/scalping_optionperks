import { Outlet } from 'react-router-dom'
import { useLiveWebSocket } from '../../hooks/useLiveWebSocket'
import { useLiveBootstrap } from '../../hooks/useLiveBootstrap'
import { useUiStore } from '../../store'
import { Sidebar } from './Sidebar'
import { TopStatusBar } from './TopStatusBar'

export function AppShell() {
  useLiveWebSocket()
  useLiveBootstrap()

  const sidebarOpen = useUiStore((s) => s.sidebarOpen)
  const setSidebarOpen = useUiStore((s) => s.setSidebarOpen)

  return (
    <div className="flex min-h-screen bg-bg">
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <Sidebar onNavigate={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col min-w-0 w-full">
        <TopStatusBar onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
