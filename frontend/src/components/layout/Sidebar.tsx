import { NavLink } from 'react-router-dom'
import { useAuthStore, useUiStore } from '../../store'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: DashboardIcon },
  { to: '/scalping', label: 'Scalping', icon: ScalpingIcon },
  { to: '/charts', label: 'Charts', icon: ChartsIcon },
  { to: '/accounts', label: 'Accounts', icon: AccountsIcon },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
]

const INDEX_LABELS: Record<string, string> = {
  NIFTY: 'Nifty 50',
  BANKNIFTY: 'Bank Nifty',
  FINNIFTY: 'Fin Nifty',
  MIDCPNIFTY: 'Midcap Nifty',
  NIFTYNXT50: 'Nifty Next 50',
}

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { email, logout } = useAuthStore()
  const collapsed = useUiStore((s) => s.sidebarCollapsed)
  const sidebarOpen = useUiStore((s) => s.sidebarOpen)
  const toggleSidebar = useUiStore((s) => s.toggleSidebar)

  return (
    <aside
      className={`fixed lg:sticky inset-y-0 left-0 z-40 shrink-0 h-screen flex flex-col border-r border-border bg-sidebar shadow-sidebar transition-transform duration-200 ease-in-out ${
        sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
      } ${collapsed ? 'w-[72px]' : 'w-56'}`}
    >
      <button
        type="button"
        onClick={toggleSidebar}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        className="hidden lg:flex absolute -right-3 top-[72px] z-40 w-6 h-6 rounded-full border border-border bg-surface shadow-card items-center justify-center text-text-muted hover:text-text hover:border-border-strong transition-colors"
      >
        <ChevronIcon collapsed={collapsed} />
      </button>

      <div className={`border-b border-border ${collapsed ? 'px-3 py-5' : 'px-5 py-5'}`}>
        <div className={`flex items-center ${collapsed ? 'justify-center' : 'gap-2.5'}`}>
          <div className="w-9 h-9 rounded-btn bg-primary-navy flex items-center justify-center shrink-0">
            <PulseIcon className="w-5 h-5 text-white" />
          </div>
          {!collapsed && (
            <span className="font-display font-bold text-lg text-primary-navy tracking-tight">ScalpDesk</span>
          )}
        </div>
      </div>

      <nav className={`flex-1 py-4 space-y-1 ${collapsed ? 'px-2' : 'px-3'}`}>
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            title={collapsed ? label : undefined}
            onClick={onNavigate}
            className={({ isActive }) =>
              `nav-item ${collapsed ? 'justify-center px-0' : ''} ${isActive ? 'nav-item-active' : ''}`
            }
          >
            <Icon className="w-[18px] h-[18px] shrink-0" />
            {!collapsed && label}
          </NavLink>
        ))}
      </nav>

      <div className={`border-t border-border space-y-3 ${collapsed ? 'px-2 py-4' : 'px-4 py-4'}`}>
        {!collapsed && (
          <p className="text-xs text-text-faint px-1">
            Logged in as <span className="font-semibold text-text">{email?.split('@')[0] ?? 'User'}</span>
          </p>
        )}
        <button
          onClick={logout}
          title={collapsed ? 'Logout' : undefined}
          className={`nav-item w-full text-down hover:bg-down/5 hover:text-down ${collapsed ? 'justify-center px-0' : ''}`}
        >
          <LogoutIcon className="w-[18px] h-[18px]" />
          {!collapsed && 'Logout'}
        </button>
      </div>
    </aside>
  )
}

function ChevronIcon({ collapsed }: { collapsed: boolean }) {
  return (
    <svg
      className={`w-3.5 h-3.5 transition-transform ${collapsed ? '' : 'rotate-180'}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
    >
      <path d="M9 18l6-6-6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function PulseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 12h4l2-7 4 14 2-7h6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function DashboardIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  )
}

function ScalpingIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ChartsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M4 20V10M10 20V4M16 20v-8M22 20V8" strokeLinecap="round" />
    </svg>
  )
}

function AccountsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" strokeLinecap="round" />
    </svg>
  )
}

function SettingsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" strokeLinecap="round" />
    </svg>
  )
}

function LogoutIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export { INDEX_LABELS }
