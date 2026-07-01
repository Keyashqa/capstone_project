import { useEffect, useState } from 'react'
import { apiGetWallet, apiTopup, type Transaction, type JobReceipt } from '../api'
import Sidebar from '../components/Sidebar'

interface Props {
  token: string
  email: string
  onNavigate: (page: 'chat' | 'wallet' | 'marketplace') => void
  onLogout: () => void
}

const TOPUP_AMOUNTS = [500, 1000, 2000, 5000]

const REASON_LABELS: Record<string, string> = {
  topup: 'Wallet top-up',
  hire_escrow: 'Paid for a task',
  completion_refund: 'Refund',
  payout: 'Payout',
}
function prettyReason(t: Transaction): string {
  if (t.job) return t.delta_cents > 0 ? 'Refund' : `Hired ${t.job.agent_name}`
  return REASON_LABELS[t.reason] ?? t.reason
}

function JobDetail({ job }: { job: JobReceipt }) {
  const fmt$ = (c: number) => `$${(c / 100).toFixed(2)}`
  const score = job.verification?.advisory_score
  const statusTone =
    job.status === 'completed' ? 'ok' : job.status === 'refunded' ? 'warn' : 'default'
  return (
    <div className="job-detail">
      <div className="job-detail-head">
        <span className={`job-badge job-badge-${statusTone}`}>
          {job.status === 'completed' ? '✓ Delivered' : job.status === 'refunded' ? '↺ Refunded' : job.status}
        </span>
        <span className="job-agent">{job.agent_name}</span>
      </div>

      <div className="job-section-label">What you asked for</div>
      <div className="job-goal">“{job.goal}”</div>

      {job.output && (
        <>
          <div className="job-section-label">What was delivered</div>
          <div className="job-output">{job.output}</div>
        </>
      )}

      {job.doc_url && (
        <a className="job-doc-link" href={job.doc_url} target="_blank" rel="noreferrer">
          <span className="job-doc-icon">📄</span>
          <span>Open in Google Docs</span>
          <span className="job-doc-arrow">↗</span>
        </a>
      )}

      {job.tools.length > 0 && (
        <div className="job-tools">
          <span className="job-section-label">Tools used</span>
          {job.tools.map(t => <code key={t} className="job-tool-chip">{t}</code>)}
        </div>
      )}

      <div className="job-meta">
        {typeof score === 'number' && (
          <div className="job-meta-row"><span>Quality score</span><b>{score}/10</b></div>
        )}
        <div className="job-meta-row"><span>Base fee</span><b>{fmt$(job.base_fee_cents)}</b></div>
        <div className="job-meta-row"><span>Completion fee</span><b>{fmt$(job.completion_fee_cents)}</b></div>
        <div className="job-meta-row job-meta-total"><span>Total</span><b>{fmt$(job.total_cents)}</b></div>
      </div>

      <div className="job-ids">
        {job.booking_id && <div><span>Booking</span><code>{job.booking_id}</code></div>}
        {job.txn_id && <div><span>Txn</span><code>{job.txn_id}</code></div>}
        {job.grant_id && <div><span>Grant</span><code>{job.grant_id}</code></div>}
      </div>
    </div>
  )
}

export default function Wallet({ token, email, onNavigate, onLogout }: Props) {
  const [balance, setBalance] = useState(0)
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [topping, setTopping] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)

  const load = async () => {
    try {
      const d = await apiGetWallet(token)
      setBalance(d.balanceCents)
      setTransactions(d.transactions)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const topup = async (cents: number) => {
    setTopping(true)
    try {
      const b = await apiTopup(token, cents)
      setBalance(b)
      await load()
    } finally { setTopping(false) }
  }

  const fmt$ = (c: number) => `$${(c / 100).toFixed(2)}`

  return (
    <div className="app-shell">
      <Sidebar
        active="wallet"
        email={email}
        balanceCents={loading ? undefined : balance}
        onNavigate={onNavigate}
        onLogout={onLogout}
      />

      <div className="wallet-main">
      <main className="page-wide">
        <div className="balance-card">
          <div className="balance-card-bg" />
          <div className="balance-label">
            <span className="mpay-tag"><span className="mpay-tag-m">M</span>Pay</span> balance
          </div>
          <div className="balance-amount">{loading ? '…' : fmt$(balance)}</div>
          <div className="topup-row">
            <span className="topup-hint">Add funds</span>
            {TOPUP_AMOUNTS.map(amt => (
              <button key={amt} className="topup-btn" onClick={() => topup(amt)} disabled={topping}>
                + {fmt$(amt)}
              </button>
            ))}
          </div>
        </div>

        <section>
          <h3>Transaction history</h3>
          {transactions.length === 0 ? (
            <div className="txn-empty">No transactions yet. Top up to get started.</div>
          ) : (
            <div className="txn-list">
              {transactions.map(t => {
                const hasJob = !!t.job
                const open = expanded === t.id
                return (
                  <div key={t.id} className={`txn-group${open ? ' txn-open' : ''}`}>
                    <div
                      className={`txn-item${hasJob ? ' txn-clickable' : ''}`}
                      onClick={() => hasJob && setExpanded(open ? null : t.id)}
                    >
                      <span className={`txn-icon${t.delta_cents > 0 ? ' txn-icon-credit' : ' txn-icon-debit'}`}>
                        {t.delta_cents > 0 ? '↓' : '↑'}
                      </span>
                      <div className="txn-main">
                        <div className="txn-reason">{prettyReason(t)}</div>
                        <div className="txn-label">
                          {t.job ? `${t.job.agent_name} · ${t.job.goal.slice(0, 46)}${t.job.goal.length > 46 ? '…' : ''}` : (t.reference_id || '—')}
                        </div>
                      </div>
                      <div className="txn-amount">
                        <span className={t.delta_cents > 0 ? 'txn-credit' : 'txn-debit'}>
                          {t.delta_cents > 0 ? '+' : ''}{fmt$(t.delta_cents)}
                        </span>
                        <div className="txn-label">{new Date(t.created_at).toLocaleString()}</div>
                      </div>
                      {hasJob && <span className={`txn-chevron${open ? ' txn-chevron-open' : ''}`}>⌄</span>}
                    </div>
                    {open && t.job && <JobDetail job={t.job} />}
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
