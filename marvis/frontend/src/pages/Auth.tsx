import { useState } from 'react'
import { apiLogin, apiRegister, type AuthState } from '../api'
import { BrandMark } from '../components/Sidebar'
import BrandWord from '../components/BrandWord'

interface Props {
  onAuth: (state: AuthState) => void
  onBack?: () => void
  initialMode?: 'login' | 'register'
}

export default function Auth({ onAuth, onBack, initialMode = 'login' }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>(initialMode)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [pin, setPin] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const state = mode === 'login'
        ? await apiLogin(email, password)
        : await apiRegister(email, password, pin)
      onAuth(state)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="auth-card">
        <div className="auth-brand">
          <BrandMark size={44} />
          <span className="auth-wordmark"><BrandWord text="Marvis" /></span>
        </div>
        <h1>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h1>
        <p className="auth-subtitle">
          {mode === 'login'
            ? 'Sign in to your AI orchestrator.'
            : 'Your personal AI orchestrator that hires and pays agents to get work done.'}
        </p>
        <form onSubmit={submit}>
          <div className="form-group">
            <label>Email</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} required />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} required />
          </div>
          {mode === 'register' && (
            <div className="form-group">
              <label>PIN (4-6 digits — used to confirm payments)</label>
              <input
                type="password" inputMode="numeric" maxLength={6}
                value={pin} onChange={e => setPin(e.target.value)}
                placeholder="e.g. 1234" required
              />
            </div>
          )}
          {error && <p className="error-msg">{error}</p>}
          <button className="btn-primary" type="submit" disabled={loading}>
            {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>
        <button
          className="link-btn"
          onClick={() => { setMode(m => m === 'login' ? 'register' : 'login'); setError('') }}
        >
          {mode === 'login' ? "Don't have an account? Register" : 'Already registered? Sign In'}
        </button>
        {onBack && (
          <button className="auth-back" onClick={onBack}>← Back to home</button>
        )}
      </div>
    </div>
  )
}
