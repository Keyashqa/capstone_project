type NavPage = 'chat' | 'wallet' | 'marketplace'

interface Props {
  active: NavPage
  email: string
  balanceCents?: number
  onNavigate: (page: NavPage) => void
  onLogout: () => void
}

const fmt$ = (c: number) => `$${(c / 100).toFixed(2)}`

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

export default function Sidebar({ active, email, balanceCents, onNavigate, onLogout }: Props) {
  const initial = (email || '?').trim().charAt(0).toUpperCase()

  return (
    <aside className="sidebar">
      <button className="brand" onClick={() => onNavigate('chat')}>
        <BrandMark />
        <span className="brand-name">Marvis</span>
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
          <span className="side-label">Marketplace</span>
        </button>
        <button
          className={`side-item${active === 'wallet' ? ' side-item-active' : ''}`}
          onClick={() => onNavigate('wallet')}
        >
          <WalletIcon />
          <span className="side-label">MPay</span>
        </button>
      </nav>

      <div className="side-bottom">
        {balanceCents !== undefined && (
          <button className="side-balance" onClick={() => onNavigate('wallet')} title="MPay balance">
            <span className="balance-pill-dot" />
            {fmt$(balanceCents)}
            <span className="side-balance-label">MPay balance</span>
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
