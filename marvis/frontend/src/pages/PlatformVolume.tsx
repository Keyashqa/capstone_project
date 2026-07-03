import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Sidebar from '../components/Sidebar'
import { apiGetPlatformStats, type PlatformStats } from '../api'

interface Props {
  email: string
  token: string
  onNavigate: (page: 'chat' | 'wallet' | 'marketplace' | 'owned-skills' | 'platform' | 'sell' | 'contributed') => void
  onLogout: () => void
}

const fmt$ = (c: number) => `$${(c / 100).toFixed(2)}`
const POLL_MS = 5000

const KPI_ICONS: Record<string, { icon: string; bg: string; fg: string }> = {
  paid: { icon: '⚡', bg: 'var(--primary-light)', fg: 'var(--primary)' },
  broker: { icon: '🏦', bg: 'var(--gold-bg)', fg: 'var(--gold)' },
  commission: { icon: '🏷️', bg: 'var(--gold-bg)', fg: 'var(--gold)' },
  refunded: { icon: '↩️', bg: 'var(--red-bg)', fg: 'var(--red)' },
  hires: { icon: '🤝', bg: 'var(--green-bg)', fg: 'var(--green)' },
}

function dayLabel(day: string): string {
  const d = new Date(`${day}T00:00:00`)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export default function PlatformVolume({ email, token, onNavigate, onLogout }: Props) {
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

  // ── "Where the money goes" — a part-to-whole breakdown of total volume.
  // Segments always sum to `volume`: whatever isn't paid out, kept as broker
  // revenue, or refunded is still sitting in escrow mid-flight.
  const flowSegments = useMemo(() => {
    if (!stats) return []
    const paid = stats.total_paid_to_agents_cents
    const broker = stats.broker_revenue_cents ?? 0
    const refunded = stats.total_refunded_cents
    const pending = Math.max(0, volume - (paid + broker + refunded))
    return [
      { key: 'paid', label: 'Paid to agents', value: paid, color: 'var(--primary)' },
      { key: 'broker', label: 'Broker revenue', value: broker, color: 'var(--gold)' },
      { key: 'refunded', label: 'Refunded', value: refunded, color: 'var(--red)' },
      { key: 'pending', label: 'In escrow (pending)', value: pending, color: 'var(--border)' },
    ].filter(s => s.value > 0)
  }, [stats, volume])

  // ── "Hiring activity" — recent hire volume, bucketed by day from the same
  // ledger feed the old raw activity list used, aggregated instead of dumped.
  const daily = useMemo(() => {
    if (!stats) return []
    const byDay = new Map<string, { count: number; cents: number }>()
    for (const e of stats.feed) {
      if (e.reason !== 'hire_escrow') continue
      const day = e.created_at.slice(0, 10)
      const cur = byDay.get(day) ?? { count: 0, cents: 0 }
      cur.count += 1
      cur.cents += e.amount_cents
      byDay.set(day, cur)
    }
    return Array.from(byDay.entries())
      .map(([day, v]) => ({ day, ...v }))
      .sort((a, b) => a.day.localeCompare(b.day))
      .slice(-14)
  }, [stats])
  const maxDailyCents = Math.max(1, ...daily.map(d => d.cents))

  return (
    <div className="app-shell">
      <Sidebar
        active="platform"
        email={email}
        token={token}
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
            <div className="gpay-stat-grid">
              <div className="gpay-stat-tile">
                <div className="gpay-stat-icon" style={{ background: KPI_ICONS.paid.bg, color: KPI_ICONS.paid.fg }}>{KPI_ICONS.paid.icon}</div>
                <div>
                  <div className="gpay-stat-num">{fmt$(stats.total_paid_to_agents_cents)}</div>
                  <div className="gpay-stat-label">Paid to agents</div>
                </div>
              </div>
              <div className="gpay-stat-tile">
                <div className="gpay-stat-icon" style={{ background: KPI_ICONS.broker.bg, color: KPI_ICONS.broker.fg }}>{KPI_ICONS.broker.icon}</div>
                <div>
                  <div className="gpay-stat-num">{fmt$(stats.broker_revenue_cents ?? 0)}</div>
                  <div className="gpay-stat-label">Broker revenue</div>
                </div>
              </div>
              <div className="gpay-stat-tile">
                <div className="gpay-stat-icon" style={{ background: KPI_ICONS.commission.bg, color: KPI_ICONS.commission.fg }}>{KPI_ICONS.commission.icon}</div>
                <div>
                  <div className="gpay-stat-num">{fmt$(stats.commission_cents ?? 0)}</div>
                  <div className="gpay-stat-label">Commission (10%)</div>
                </div>
              </div>
              <div className="gpay-stat-tile">
                <div className="gpay-stat-icon" style={{ background: KPI_ICONS.refunded.bg, color: KPI_ICONS.refunded.fg }}>{KPI_ICONS.refunded.icon}</div>
                <div>
                  <div className="gpay-stat-num">{fmt$(stats.total_refunded_cents)}</div>
                  <div className="gpay-stat-label">Refunded</div>
                </div>
              </div>
              <div className="gpay-stat-tile">
                <div className="gpay-stat-icon" style={{ background: KPI_ICONS.hires.bg, color: KPI_ICONS.hires.fg }}>{KPI_ICONS.hires.icon}</div>
                <div>
                  <div className="gpay-stat-num">{stats.hire_count}</div>
                  <div className="gpay-stat-label">Hires</div>
                </div>
              </div>
            </div>
          )}

          {!loading && stats && flowSegments.length > 0 && (
            <div className="viz-card">
              <div className="viz-card-title">Where the money goes</div>
              <p className="viz-card-sub">Every dollar committed to a hire, split by where it ended up.</p>

              <div className="flow-bar">
                {flowSegments.map(s => (
                  <div
                    key={s.key}
                    className="flow-bar-seg"
                    data-tip={`${s.label}: ${fmt$(s.value)} (${((s.value / volume) * 100).toFixed(1)}%)`}
                    style={{ width: `${(s.value / volume) * 100}%`, background: s.color }}
                    tabIndex={0}
                  />
                ))}
              </div>

              <div className="flow-legend">
                {flowSegments.map(s => (
                  <div className="flow-legend-item" key={s.key}>
                    <span className="flow-legend-dot" style={{ background: s.color }} />
                    <span className="flow-legend-label">{s.label}</span>
                    <span className="flow-legend-value">{fmt$(s.value)}</span>
                    <span className="flow-legend-pct">{((s.value / volume) * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!loading && stats && (
            <div className="viz-card">
              <div className="viz-card-title">Hiring activity</div>
              <p className="viz-card-sub">Hire volume per day, most recent {daily.length || 0} day{daily.length === 1 ? '' : 's'} of activity.</p>

              {daily.length === 0 ? (
                <div className="txn-empty">No hiring activity yet. Hire a skill from the Marketplace to see it here.</div>
              ) : (
                <div className="trend-chart">
                  {daily.map(d => (
                    <div className="trend-bar-col" key={d.day}>
                      <div
                        className="trend-bar"
                        data-tip={`${dayLabel(d.day)}: ${d.count} hire${d.count === 1 ? '' : 's'} · ${fmt$(d.cents)}`}
                        style={{ height: `${Math.max(4, (d.cents / maxDailyCents) * 100)}%` }}
                        tabIndex={0}
                      />
                      <div className="trend-bar-axis">{dayLabel(d.day)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
