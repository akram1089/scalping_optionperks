import { Outlet } from 'react-router-dom'
import { useLiveWebSocket } from '../../hooks/useLiveWebSocket'
import { Sidebar } from './Sidebar'
import { TopStatusBar } from './TopStatusBar'

export function AppShell() {
  useLiveWebSocket()

  return (
    <div className="flex min-h-screen bg-bg">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopStatusBar />
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
