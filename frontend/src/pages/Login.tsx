import { Link, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { LandingNav } from '../components/layout/LandingNav'
import { useAuthStore } from '../store'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const login = useAuthStore((s) => s.login)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await login(email, password)
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    }
  }

  return (
    <div className="min-h-screen bg-bg bg-grid bg-grid">
      <LandingNav />
      <div className="flex items-center justify-center px-4 py-16">
        <form onSubmit={handleSubmit} className="card w-full max-w-md p-8 shadow-elevated">
          <h1 className="font-display text-2xl font-bold text-primary-navy">Sign in</h1>
          <p className="text-sm text-text-muted mt-1 mb-6">Access your trading terminal</p>
          {error && <div className="mb-4 p-3 rounded-btn bg-down/10 text-down text-sm">{error}</div>}
          <label className="block text-xs font-semibold uppercase tracking-wider text-text-faint mb-1.5">Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="input-field mb-4" required />
          <label className="block text-xs font-semibold uppercase tracking-wider text-text-faint mb-1.5">Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="input-field mb-6" required />
          <button type="submit" className="btn-primary w-full py-3">Sign In</button>
          <p className="text-sm text-text-muted mt-5 text-center">
            No account? <Link to="/signup" className="text-primary font-semibold hover:underline">Create one</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
