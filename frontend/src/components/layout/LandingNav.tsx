import { Link, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../store'

const links = [
  { href: '#features', label: 'Features' },
  { href: '#technology', label: 'Technology' },
  { href: '#risk', label: 'Risk Controls' },
]

export function LandingNav() {
  const { isAuthenticated } = useAuthStore()
  const location = useLocation()
  const isAuthPage = location.pathname === '/login' || location.pathname === '/signup'

  return (
    <header className="sticky top-0 z-50 bg-surface/80 backdrop-blur-md border-b border-border/60">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-primary-navy flex items-center justify-center">
            <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 12h4l2-7 4 14 2-7h6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <span className="font-display font-bold text-lg text-primary-navy">ScalpDesk</span>
        </Link>

        {!isAuthPage && (
          <nav className="hidden md:flex items-center gap-8">
            {links.map((l) => (
              <a key={l.href} href={l.href} className="text-sm font-medium text-text-muted hover:text-text transition-colors">
                {l.label}
              </a>
            ))}
          </nav>
        )}

        <div className="flex items-center gap-3">
          {isAuthenticated ? (
            <Link to="/dashboard" className="btn-primary text-sm py-2">Open Terminal</Link>
          ) : (
            <>
              <Link to="/login" className="text-sm font-medium text-text-muted hover:text-text px-3 py-2">
                Sign In
              </Link>
              <Link to="/signup" className="btn-primary text-sm py-2">Get Started</Link>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
