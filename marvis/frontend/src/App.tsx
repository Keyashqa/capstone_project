import { useState, useEffect } from 'react'
import Landing from './pages/Landing'
import Auth from './pages/Auth'
import Wallet from './pages/Wallet'
import Chat from './pages/Chat'
import Marketplace from './pages/Marketplace'
import OwnedSkills from './pages/OwnedSkills'
import PlatformVolume from './pages/PlatformVolume'
import SellSkill from './pages/SellSkill'
import type { AuthState } from './api'
import './App.css'

type Page = 'landing' | 'auth' | 'wallet' | 'chat' | 'marketplace' | 'owned-skills' | 'platform' | 'sell'

const STORAGE_KEY = 'marvis_auth'

function loadAuth(): AuthState | null {
  try {
    const s = localStorage.getItem(STORAGE_KEY)
    return s ? JSON.parse(s) : null
  } catch { return null }
}

function saveAuth(state: AuthState) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function clearAuth() {
  localStorage.removeItem(STORAGE_KEY)
}

export default function App() {
  const [auth, setAuth] = useState<AuthState | null>(loadAuth)
  const [page, setPage] = useState<Page>(auth ? 'wallet' : 'landing')
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login')

  useEffect(() => {
    if (!auth && page !== 'auth' && page !== 'landing') setPage('landing')
  }, [auth, page])

  const handleAuth = (state: AuthState) => {
    saveAuth(state)
    setAuth(state)
    setPage('wallet')
  }

  const handleLogout = () => {
    clearAuth()
    setAuth(null)
    setPage('landing')
  }

  const handleBalanceChange = (cents: number) => {
    if (auth) {
      const updated = { ...auth, balanceCents: cents }
      saveAuth(updated)
      setAuth(updated)
    }
  }

  const goToAuth = (mode: 'login' | 'register') => {
    setAuthMode(mode)
    setPage('auth')
  }

  if (!auth) {
    if (page === 'auth') {
      return <Auth initialMode={authMode} onAuth={handleAuth} onBack={() => setPage('landing')} />
    }
    return (
      <Landing
        onGetStarted={() => goToAuth('register')}
        onSignIn={() => goToAuth('login')}
      />
    )
  }

  if (page === 'chat') {
    return (
      <Chat
        auth={auth}
        onNavigate={setPage}
        onLogout={handleLogout}
        onBalanceChange={handleBalanceChange}
      />
    )
  }

  if (page === 'marketplace') {
    return (
      <Marketplace
        email={auth.email}
        balanceCents={auth.balanceCents}
        onNavigate={setPage}
        onLogout={handleLogout}
      />
    )
  }

  if (page === 'owned-skills') {
    return (
      <OwnedSkills
        email={auth.email}
        balanceCents={auth.balanceCents}
        onNavigate={setPage}
        onLogout={handleLogout}
      />
    )
  }

  if (page === 'platform') {
    return (
      <PlatformVolume
        email={auth.email}
        balanceCents={auth.balanceCents}
        onNavigate={setPage}
        onLogout={handleLogout}
      />
    )
  }

  if (page === 'sell') {
    return (
      <SellSkill
        token={auth.token}
        email={auth.email}
        balanceCents={auth.balanceCents}
        onNavigate={setPage}
        onLogout={handleLogout}
      />
    )
  }

  return (
    <Wallet
      token={auth.token}
      email={auth.email}
      onNavigate={setPage}
      onLogout={handleLogout}
    />
  )
}
