import { Link, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { LandingNav } from '../components/layout/LandingNav'
import { useAuthStore } from '../store'

export function SignupPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const signup = useAuthStore((s) => s.signup)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await signup(email, password)
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signup failed')
    }
  }

  return (
    <div className="min-h-screen bg-bg bg-grid bg-grid">
      <LandingNav />
      <div className="flex items-center justify-center px-4 py-16">
        <form onSubmit={handleSubmit} className="card w-full max-w-md p-8 shadow-elevated">
          <h1 className="font-display text-2xl font-bold text-primary-navy">Create account</h1>
          <p className="text-sm text-text-muted mt-1 mb-6">Start with paper trading — always</p>
          {error && <div className="mb-4 p-3 rounded-btn bg-down/10 text-down text-sm">{error}</div>}
          <label className="block text-xs font-semibold uppercase tracking-wider text-text-faint mb-1.5">Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="input-field mb-4" required />
          <label className="block text-xs font-semibold uppercase tracking-wider text-text-faint mb-1.5">Password (min 8)</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} className="input-field mb-6" required />
          <button type="submit" className="btn-accent w-full py-3">Create Account</button>
          <p className="text-sm text-text-muted mt-5 text-center">
            Have an account? <Link to="/login" className="text-primary font-semibold hover:underline">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
