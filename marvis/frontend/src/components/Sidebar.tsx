import { useEffect, useState } from 'react'
import { apiGetWallet } from '../api'
import { onBalanceChanged } from '../balanceBus'
import BrandWord from './BrandWord'

type NavPage = 'chat' | 'wallet' | 'marketplace' | 'owned-skills' | 'platform' | 'sell' | 'contributed' | 'about'

interface Props {
  active: NavPage
  email: string
  token: string
  onNavigate: (page: NavPage) => void
  onLogout: () => void
}

const fmt$ = (c: number) => `$${(c / 100).toFixed(2)}`
const BALANCE_POLL_MS = 5000

export function BrandMark({ size = 30 }: { size?: number }) {
  return (
    <span className="brand-mark" style={{ width: size, height: size }} aria-hidden>
      <svg viewBox="0 0 24 24" width={size * 0.62} height={size * 0.62} fill="none">
        <path
          d="M4 18V7.5a1 1 0 0 1 1.7-.7L12 13l6.3-6.2a1 1 0 0 1 1.7.7V18"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  )
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M4 5h16v11H8l-4 4V5z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  )
}

function WalletIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="3" y="6" width="18" height="13" rx="2.5" stroke="currentColor" strokeWidth="1.8" />
      <path d="M3 10.5h18" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="16.5" cy="14.8" r="1.3" fill="currentColor" />
    </svg>
  )
}

function MarketIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M4 9h16l-1 10H5L4 9z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M4 9l1.5-4h13L20 9" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M9 13c0 1.7 1.3 3 3 3s3-1.3 3-3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  )
}

function OwnedSkillsIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="7" y="7" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3"
        stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      />
    </svg>
  )
}

function PlatformIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M4 20V10M11 20V4M18 20v-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M3 20h18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  )
}

function SellIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  )
}

function ContributedIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M7 20V10M12 20V4M17 20v-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="7" cy="7" r="2.2" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  )
}

function AboutIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
      <path d="M12 11v5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="12" cy="7.8" r="1.1" fill="currentColor" />
    </svg>
  )
}

export default function Sidebar({ active, email, token, onNavigate, onLogout }: Props) {
  const initial = (email || '?').trim().charAt(0).toUpperCase()
  const [balanceCents, setBalanceCents] = useState<number | undefined>(undefined)

  // Always fetch live — a stale balance baked into login-time state was the
  // source of MPay vs. Chat showing two different numbers. Polling also picks
  // up balance changes made without leaving the current page (e.g. mid-chat
  // hire payments).
  useEffect(() => {
    if (!token) return
    let cancelled = false
    const refresh = () => {
      apiGetWallet(token)
        .then(d => { if (!cancelled) setBalanceCents(d.balanceCents) })
        .catch(() => { /* keep last-known value on transient failure */ })
    }
    refresh()
    const id = setInterval(refresh, BALANCE_POLL_MS)
    const unsubscribe = onBalanceChanged(refresh)
    return () => { cancelled = true; clearInterval(id); unsubscribe() }
  }, [token])

  return (
    <aside className="sidebar">
      <button className="brand" onClick={() => onNavigate('chat')}>
        <BrandMark />
        <span className="brand-name"><BrandWord text="Marvis" /></span>
      </button>

      <nav className="side-nav">
        <button
          className={`side-item${active === 'chat' ? ' side-item-active' : ''}`}
          onClick={() => onNavigate('chat')}
        >
          <ChatIcon />
          <span className="side-label">Chat</span>
        </button>
        <button
          className={`side-item${active === 'marketplace' ? ' side-item-active' : ''}`}
          onClick={() => onNavigate('marketplace')}
        >
          <MarketIcon />
          <span className="side-label">Skills <BrandWord text="Marketplace" /></span>
        </button>
        <button
          className={`side-item${active === 'owned-skills' ? ' side-item-active' : ''}`}
          onClick={() => onNavigate('owned-skills')}
        >
          <OwnedSkillsIcon />
          <span className="side-label">Owned Skills</span>
        </button>
        <button
          className={`side-item${active === 'sell' ? ' side-item-active' : ''}`}
          onClick={() => onNavigate('sell')}
        >
          <SellIcon />
          <span className="side-label">Contribute Skills</span>
        </button>
        <button
          className={`side-item${active === 'contributed' ? ' side-item-active' : ''}`}
          onClick={() => onNavigate('contributed')}
        >
          <ContributedIcon />
          <span className="side-label">Contributed Skills</span>
        </button>
        <button
          className={`side-item${active === 'platform' ? ' side-item-active' : ''}`}
          onClick={() => onNavigate('platform')}
        >
          <PlatformIcon />
          <span className="side-label">Platform Volume</span>
        </button>
        <button
          className={`side-item${active === 'about' ? ' side-item-active' : ''}`}
          onClick={() => onNavigate('about')}
        >
          <AboutIcon />
          <span className="side-label">About Platform</span>
        </button>
        <button
          className={`side-item${active === 'wallet' ? ' side-item-active' : ''}`}
          onClick={() => onNavigate('wallet')}
        >
          <WalletIcon />
          <span className="side-label"><BrandWord text="MPay" /></span>
        </button>
      </nav>

      <div className="side-bottom">
        {balanceCents !== undefined && (
          <button className="side-balance" onClick={() => onNavigate('wallet')} title="MPay balance">
            <span className="balance-pill-dot" />
            {fmt$(balanceCents)}
            <span className="side-balance-label"><BrandWord text="MPay" /> balance</span>
          </button>
        )}
        <div className="side-account">
          <span className="account-avatar" title={email}>{initial}</span>
          <div className="side-account-info">
            <span className="side-email">{email}</span>
            <button className="sign-out" onClick={onLogout}>Sign out</button>
          </div>
        </div>
      </div>
    </aside>
  )
}
