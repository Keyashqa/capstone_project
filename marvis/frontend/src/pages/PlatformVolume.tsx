import { useCallback, useEffect, useRef, useState } from 'react'
import Sidebar from '../components/Sidebar'
import { apiGetPlatformStats, type PlatformFeedEvent, type PlatformStats } from '../api'

interface Props {
  email: string
  balanceCents: number
  onNavigate: (page: 'chat' | 'wallet' | 'marketplace' | 'owned-skills' | 'platform' | 'sell') => void
  onLogout: () => void
}

const fmt$ = (c: number) => `$${(c / 100).toFixed(2)}`
const POLL_MS = 5000

const FEED_META: Record<string, { icon: string; tone: 'credit' | 'debit'; label: (e: PlatformFeedEvent) => string }> = {
  topup: { icon: '💰', tone: 'credit', label: () => 'Wallet top-up' },
  hire_escrow: { icon: '🤝', tone: 'credit', label: () => 'New hire — funds moved to escrow' },
  payout: {
    icon: '✅',
    tone: 'credit',
    label: e => `Paid to ${e.to_account.replace(/^agent:/, '')}`,
  },
  payout_owner: {
    icon: '✅',
    tone: 'credit',
    label: e => `Owner earnings → ${e.to_account.replace(/^agent:owner:/, '')}`,
  },
  payout_commission: { icon: '🏦', tone: 'credit', label: () => 'Broker commission (10%)' },
  payout_broker: { icon: '🏦', tone: 'credit', label: () => 'Broker payout (unowned skill)' },
  completion_refund: { icon: '↩️', tone: 'debit', label: () => 'Completion fee refunded' },
  build_completion_refund: { icon: '↩️', tone: 'debit', label: () => 'Build fee refunded' },
}

function feedMeta(e: PlatformFeedEvent) {
  return FEED_META[e.reason] ?? { icon: '•', tone: 'credit' as const, label: () => e.reason }
}

export default function PlatformVolume({ email, balanceCents, onNavigate, onLogout }: Props) {
  const [stats, setStats] = useState<PlatformStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async (showSpinner: boolean) => {
    if (showSpinner) setRefreshing(true)
    try {
      const d = await apiGetPlatformStats()
      setStats(d)
      setError('')
    } catch {
      setError('Could not reach Marvis (is it running on :8000?)')
    } finally {
      setLoading(false)
      if (showSpinner) setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    load(false)
    pollRef.current = setInterval(() => load(false), POLL_MS)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [load])

  const volume = stats?.total_volume_cents ?? 0
  const hasActivity = (stats?.hire_count ?? 0) > 0

  return (
    <div className="app-shell">
      <Sidebar
        active="platform"
        email={email}
        balanceCents={balanceCents}
        onNavigate={onNavigate}
        onLogout={onLogout}
      />

      <div className="wallet-main">
        <main className="page-wide">
          <div className="balance-card">
            <div className="balance-card-bg" />
            <div className="balance-label">
              Total marketplace volume
              <button className="volume-refresh" onClick={() => load(true)} disabled={refreshing} title="Refresh now">
                {refreshing ? '↻ …' : '↻ Refresh'}
              </button>
            </div>
            <div className="balance-amount">{loading ? '…' : fmt$(volume)}</div>
            <div className="topup-hint">Every dollar every user has ever committed to a hire, live from the ledger</div>
          </div>

          {error && <div className="market-note market-note-error">{error}</div>}

          {!loading && stats && (
            <div className="market-stats platform-stats-row">
              <div className="market-stat">
                <div className="market-stat-num">{fmt$(stats.total_paid_to_agents_cents)}</div>
                <div className="market-stat-label">Paid to agents</div>
              </div>
              <div className="market-stat">
                <div className="market-stat-num">{fmt$(stats.broker_revenue_cents ?? 0)}</div>
                <div className="market-stat-label">Broker revenue</div>
              </div>
              <div className="market-stat">
                <div className="market-stat-num">{fmt$(stats.commission_cents ?? 0)}</div>
                <div className="market-stat-label">Commission (10%)</div>
              </div>
              <div className="market-stat">
                <div className="market-stat-num">{fmt$(stats.total_refunded_cents)}</div>
                <div className="market-stat-label">Refunded</div>
              </div>
              <div className="market-stat">
                <div className="market-stat-num">{stats.hire_count}</div>
                <div className="market-stat-label">Hires</div>
              </div>
            </div>
          )}

          {!loading && stats && (stats.per_owner?.length ?? 0) > 0 && (
            <section>
              <h3>Seller earnings</h3>
              <div className="txn-list">
                {stats.per_owner.map(o => (
                  <div className="txn-item" key={o.owner_id}>
                    <span className="txn-icon txn-icon-credit">🧑‍💼</span>
                    <div className="txn-main">
                      <div className="txn-reason">{o.owner_id}</div>
                      <div className="txn-label">Base (100%) + completion (90%) across all hires</div>
                    </div>
                    <div className="txn-amount">
                      <span className="txn-credit">{fmt$(o.earned_cents)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {!loading && stats && stats.per_agent.length > 0 && (
            <section>
              <h3>Earnings by agent</h3>
              <div className="txn-list">
                {stats.per_agent.map(a => (
                  <div className="txn-item" key={a.agent_name}>
                    <span className="txn-icon txn-icon-credit">⚡</span>
                    <div className="txn-main">
                      <div className="txn-reason">{a.agent_name}</div>
                      <div className="txn-label">Total earned across all hires</div>
                    </div>
                    <div className="txn-amount">
                      <span className="txn-credit">{fmt$(a.earned_cents)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section>
            <h3>Live activity</h3>
            {loading ? (
              <div className="txn-empty">Loading…</div>
            ) : !hasActivity ? (
              <div className="txn-empty">No activity yet. Hire a specialist from the Marketplace to see it here.</div>
            ) : (
              <div className="txn-list">
                {stats!.feed.map(e => {
                  const meta = feedMeta(e)
                  return (
                    <div className="txn-item" key={e.journal_id}>
                      <span className={`txn-icon${meta.tone === 'credit' ? ' txn-icon-credit' : ' txn-icon-debit'}`}>
                        {meta.icon}
                      </span>
                      <div className="txn-main">
                        <div className="txn-reason">{meta.label(e)}</div>
                        <div className="txn-label">{e.reference_id ? `task ${e.reference_id.slice(0, 12)}` : '—'}</div>
                      </div>
                      <div className="txn-amount">
                        <span className={meta.tone === 'credit' ? 'txn-credit' : 'txn-debit'}>
                          {fmt$(e.amount_cents)}
                        </span>
                        <div className="txn-label">{new Date(e.created_at).toLocaleString()}</div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </section>
        </main>
      </div>
    </div>
  )
}
