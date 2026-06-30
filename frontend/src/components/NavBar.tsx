import { Link } from 'react-router-dom'
import { useAuthStore } from '../store'

export function NavBar() {
  const { isAuthenticated, email, logout } = useAuthStore()

  return (
    <header className="border-b border-border bg-bg px-6 py-4 flex items-center justify-between">
      <Link to="/" className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-btn bg-primary-navy flex items-center justify-center text-white font-bold text-sm">
          SD
        </div>
        <span className="font-semibold text-lg text-primary-navy">ScalpDesk</span>
      </Link>
      <nav className="hidden md:flex gap-6 text-sm text-text-muted">
        {isAuthenticated && (
          <>
            <Link to="/dashboard" className="hover:text-primary">Dashboard</Link>
            <Link to="/strategies" className="hover:text-primary">Strategies</Link>
            <Link to="/charts" className="hover:text-primary">Charts</Link>
            <Link to="/accounts" className="hover:text-primary">Accounts</Link>
          </>
        )}
      </nav>
      <div className="flex items-center gap-3">
        {isAuthenticated ? (
          <>
            <span className="text-sm text-text-muted hidden sm:inline">{email}</span>
            <button onClick={logout} className="text-sm text-text-muted hover:text-text">
              Log out
            </button>
          </>
        ) : (
          <>
            <Link to="/login" className="px-4 py-2 rounded-btn text-sm font-medium text-primary hover:bg-bg-subtle">
              Sign In
            </Link>
            <Link to="/signup" className="px-4 py-2 rounded-btn text-sm font-medium bg-accent text-white hover:bg-accent-700">
              Sign Up
            </Link>
          </>
        )}
      </div>
    </header>
  )
}
