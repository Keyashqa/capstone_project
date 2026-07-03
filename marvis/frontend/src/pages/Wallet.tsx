import { useEffect, useState } from 'react'
import { apiGetWallet, apiTopup, apiVerifyPin, type Transaction, type JobReceipt } from '../api'
import Sidebar from '../components/Sidebar'
import Modal from '../components/Modal'
import BrandWord from '../components/BrandWord'
import { notifyBalanceChanged } from '../balanceBus'

interface Props {
  token: string
  email: string
  onNavigate: (page: 'chat' | 'wallet' | 'marketplace' | 'owned-skills' | 'platform' | 'sell' | 'contributed') => void
  onLogout: () => void
}

const TOPUP_AMOUNTS = [500, 1000, 2000, 5000]

const REASON_LABELS: Record<string, string> = {
  topup: 'Wallet top-up',
  hire_escrow: 'Paid for a task',
  completion_refund: 'Refund',
  payout: 'Payout',
  payout_owner: 'Skill sale earnings',
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
          {job.tools.map((t, i) => {
            const name = typeof t === 'string' ? t : (t.tool ?? JSON.stringify(t))
            return <code key={i} className="job-tool-chip">{name}</code>
          })}
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

type AddMoneyStep = 'amount' | 'confirm' | 'processing' | 'success'

const toCents = (dollars: string) => Math.round(parseFloat(dollars || '0') * 100)

export default function Wallet({ token, email, onNavigate, onLogout }: Props) {
  const [balance, setBalance] = useState(0)
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)

  const [addOpen, setAddOpen] = useState(false)
  const [addStep, setAddStep] = useState<AddMoneyStep>('amount')
  const [amountUsd, setAmountUsd] = useState('20.00')
  const [pin, setPin] = useState('')
  const [addError, setAddError] = useState('')
  const [addedCents, setAddedCents] = useState(0)

  const load = async () => {
    try {
      const d = await apiGetWallet(token)
      setBalance(d.balanceCents)
      setTransactions(d.transactions)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const fmt$ = (c: number) => `$${(c / 100).toFixed(2)}`

  const openAddMoney = () => {
    setAddStep('amount')
    setAmountUsd('20.00')
    setPin('')
    setAddError('')
    setAddOpen(true)
  }
  const closeAddMoney = () => setAddOpen(false)

  const goToConfirm = () => {
    if (toCents(amountUsd) <= 0) { setAddError('Enter an amount greater than $0.'); return }
    setAddError('')
    setAddStep('confirm')
  }

  const confirmTransfer = async () => {
    if (!/^\d{4,6}$/.test(pin)) { setAddError('Enter your 4–6 digit MPay PIN.'); return }
    setAddError('')
    const ok = await apiVerifyPin(token, pin)
    if (!ok) { setAddError('Incorrect PIN. Try again.'); return }

    const cents = toCents(amountUsd)
    setAddStep('processing')
    // Simulated ACH transfer latency — a real bank link will genuinely take a
    // moment; this stands in for that until the real integration lands.
    setTimeout(async () => {
      try {
        const b = await apiTopup(token, cents)
        setBalance(b)
        setAddedCents(cents)
        await load()
        notifyBalanceChanged()
        setAddStep('success')
      } catch {
        setAddError('Transfer failed. Please try again.')
        setAddStep('confirm')
      }
    }, 1100)
  }

  return (
    <div className="app-shell">
      <Sidebar
        active="wallet"
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
            <BrandWord text="MPay" /> balance
          </div>
          <div className="balance-amount">{loading ? '…' : fmt$(balance)}</div>
          <div className="topup-row">
            <span className="topup-hint">Add funds</span>
            <button className="topup-btn" onClick={openAddMoney}>+ Add money from bank</button>
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

      {addOpen && (
        <Modal onClose={closeAddMoney}>
          {addStep === 'amount' && (
            <>
              <h3 className="addmoney-title">Add money from bank</h3>
              <div className="bank-card">
                <div className="bank-icon">🏦</div>
                <div className="bank-id">
                  <div className="bank-name">Checking Account</div>
                  <div className="bank-mask">•••• 4821 · simulated — real bank linking coming soon</div>
                </div>
                <span className="bank-linked-badge">Linked</span>
              </div>

              <label className="sell-field" style={{ marginBottom: 14 }}>
                <span className="sell-label">Amount to transfer</span>
                <input
                  className="sell-input"
                  type="number"
                  step="1"
                  min="0"
                  value={amountUsd}
                  onChange={e => setAmountUsd(e.target.value)}
                />
              </label>

              <div className="amount-picker">
                {TOPUP_AMOUNTS.map(amt => (
                  <button
                    key={amt}
                    className={`amount-chip${toCents(amountUsd) === amt ? ' amount-chip-active' : ''}`}
                    onClick={() => setAmountUsd((amt / 100).toFixed(2))}
                  >
                    + {fmt$(amt)}
                  </button>
                ))}
              </div>

              {addError && <div className="transfer-error">{addError}</div>}

              <button className="agent-hire" style={{ width: '100%' }} onClick={goToConfirm}>
                Continue
              </button>
            </>
          )}

          {addStep === 'confirm' && (
            <>
              <h3 className="addmoney-title">Confirm transfer</h3>
              <div className="transfer-summary-amount">{fmt$(toCents(amountUsd))}</div>
              <div className="transfer-summary">
                <div className="transfer-summary-row"><span>From</span><span>Checking Account •••• 4821</span></div>
                <div className="transfer-summary-row"><span>To</span><span>MPay balance</span></div>
                <div className="transfer-summary-row"><span>Method</span><span>Simulated ACH transfer</span></div>
              </div>

              <label className="sell-field" style={{ marginBottom: 6 }}>
                <span className="sell-label" style={{ textAlign: 'center' }}>Enter your MPay PIN to authorize</span>
                <input
                  className="sell-input pin-input"
                  type="password"
                  inputMode="numeric"
                  maxLength={6}
                  autoFocus
                  value={pin}
                  onChange={e => setPin(e.target.value.replace(/\D/g, ''))}
                  onKeyDown={e => e.key === 'Enter' && confirmTransfer()}
                />
              </label>

              {addError && <div className="transfer-error" style={{ marginTop: 14 }}>{addError}</div>}

              <div style={{ display: 'flex', gap: 10, marginTop: 18 }}>
                <button className="filter-chip" style={{ flex: 1 }} onClick={() => setAddStep('amount')}>Back</button>
                <button className="agent-hire" style={{ flex: 2 }} onClick={confirmTransfer}>
                  Confirm transfer
                </button>
              </div>
            </>
          )}

          {addStep === 'processing' && (
            <div className="transfer-status">
              <div className="transfer-spinner" />
              <div className="transfer-status-text">Transferring from your bank via simulated ACH…</div>
            </div>
          )}

          {addStep === 'success' && (
            <div className="transfer-status">
              <div className="transfer-success-icon">✓</div>
              <div className="transfer-success-amount">+{fmt$(addedCents)}</div>
              <div className="transfer-status-text">Added to your MPay balance</div>
              <button className="agent-hire" onClick={closeAddMoney} style={{ marginTop: 8 }}>Done</button>
            </div>
          )}
        </Modal>
      )}
    </div>
  )
}
