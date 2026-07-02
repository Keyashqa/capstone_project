import { useState } from 'react'
import Sidebar from '../components/Sidebar'
import { apiCreateSkill, type CreatedSkill } from '../api'

interface Props {
  token: string
  email: string
  balanceCents: number
  onNavigate: (page: 'chat' | 'wallet' | 'marketplace' | 'owned-skills' | 'platform' | 'sell') => void
  onLogout: () => void
}

const fmt$ = (c: number) => `$${(c / 100).toFixed(2)}`
const toCents = (dollars: string) => Math.round(parseFloat(dollars || '0') * 100)

export default function SellSkill({ token, email, balanceCents, onNavigate, onLogout }: Props) {
  const [displayName, setDisplayName] = useState('')
  const [description, setDescription] = useState('')
  const [instruction, setInstruction] = useState('')
  const [tool, setTool] = useState<'create_doc' | 'get_doc_content'>('create_doc')
  const [keywords, setKeywords] = useState('')
  const [baseUsd, setBaseUsd] = useState('0.50')
  const [completionUsd, setCompletionUsd] = useState('1.00')

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState<CreatedSkill | null>(null)

  const keywordList = keywords.split(',').map(k => k.trim()).filter(Boolean)
  const baseCents = toCents(baseUsd)
  const completionCents = toCents(completionUsd)
  const totalCents = baseCents + completionCents
  const commissionCents = Math.floor((completionCents * 1000) / 10000) // 10% of completion
  const youKeepCents = totalCents - commissionCents

  const valid =
    displayName.trim().length > 0 &&
    instruction.trim().length > 0 &&
    keywordList.length > 0 &&
    totalCents > 0

  const submit = async () => {
    setError('')
    if (!valid) { setError('Fill in a name, an instruction, at least one keyword, and a fee.'); return }
    setSubmitting(true)
    try {
      const created = await apiCreateSkill(token, {
        display_name: displayName.trim(),
        description: description.trim(),
        instruction: instruction.trim(),
        tool_name: tool,
        match_keywords: keywordList,
        base_fee_cents: baseCents,
        completion_fee_cents: completionCents,
      })
      setDone(created)
    } catch (e: any) {
      setError(e.message || 'Failed to publish skill')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="app-shell">
      <Sidebar active="sell" email={email} balanceCents={balanceCents} onNavigate={onNavigate} onLogout={onLogout} />

      <div className="wallet-main">
        <main className="page-wide">
          <div className="market-hero">
            <span className="eyebrow">Sell a Skill</span>
            <h1>Publish a skill to the marketplace</h1>
            <p className="market-hero-sub">
              Describe a specialist you want to sell. When another user hires it, you earn its
              <b> base fee (100%)</b> plus <b>90% of the completion fee</b> — the broker keeps a 10%
              commission. Earnings land in your <b>seller account</b> (visible on Platform Volume).
            </p>
          </div>

          {done ? (
            <div className="market-note" style={{ borderColor: 'var(--green)' }}>
              <h3 style={{ marginTop: 0, color: 'var(--green)' }}>✅ Published — “{displayName}” is live</h3>
              <p>
                Skill ID <code>{done.skill_id}</code> · agent <b>@{done.agent_name}</b> · earnings route to{' '}
                <code>{done.owner_account}</code>.
              </p>
              <p>It will be hired when a task mentions: {done.match_keywords.map(k => <span className="agent-tag" key={k}>{k}</span>)}</p>
              <div className="actions-row" style={{ display: 'flex', gap: 12, marginTop: 12 }}>
                <button className="agent-hire" onClick={() => onNavigate('marketplace')}>View in Marketplace →</button>
                <button className="filter-chip" onClick={() => { setDone(null); setDisplayName(''); setDescription(''); setInstruction(''); setKeywords('') }}>
                  Publish another
                </button>
              </div>
            </div>
          ) : (
            <div className="sell-form" style={{ maxWidth: 720, display: 'grid', gap: 18 }}>
              <label className="sell-field">
                <span className="sell-label">Skill name</span>
                <input className="sell-input" placeholder="e.g. Cold Outreach Email Writer"
                  value={displayName} onChange={e => setDisplayName(e.target.value)} />
              </label>

              <label className="sell-field">
                <span className="sell-label">Short description</span>
                <input className="sell-input" placeholder="What this skill does, in one line"
                  value={description} onChange={e => setDescription(e.target.value)} />
              </label>

              <label className="sell-field">
                <span className="sell-label">Instruction (the skill's system prompt)</span>
                <textarea className="sell-input" rows={6}
                  placeholder="You are an expert cold-email copywriter. Write a concise, personalised outreach email…"
                  value={instruction} onChange={e => setInstruction(e.target.value)} />
              </label>

              <div className="sell-field">
                <span className="sell-label">Capability (the one real tool this skill uses)</span>
                <div className="market-filters">
                  <button className={`filter-chip${tool === 'create_doc' ? ' filter-chip-active' : ''}`}
                    onClick={() => setTool('create_doc')}>✍️ Writes &amp; saves a Google Doc (create_doc)</button>
                  <button className={`filter-chip${tool === 'get_doc_content' ? ' filter-chip-active' : ''}`}
                    onClick={() => setTool('get_doc_content')}>📖 Reads a Google Doc (get_doc_content)</button>
                </div>
              </div>

              <label className="sell-field">
                <span className="sell-label">Match keywords (comma-separated — how tasks find this skill)</span>
                <input className="sell-input" placeholder="email, outreach, cold email"
                  value={keywords} onChange={e => setKeywords(e.target.value)} />
                {keywordList.length > 0 && (
                  <div className="agent-tags" style={{ marginTop: 8 }}>
                    {keywordList.map(k => <span className="agent-tag" key={k}>{k}</span>)}
                  </div>
                )}
              </label>

              <div style={{ display: 'flex', gap: 18 }}>
                <label className="sell-field" style={{ flex: 1 }}>
                  <span className="sell-label">Base fee (USD, non-refundable)</span>
                  <input className="sell-input" type="number" step="0.05" min="0"
                    value={baseUsd} onChange={e => setBaseUsd(e.target.value)} />
                </label>
                <label className="sell-field" style={{ flex: 1 }}>
                  <span className="sell-label">Completion fee (USD, on delivery)</span>
                  <input className="sell-input" type="number" step="0.05" min="0"
                    value={completionUsd} onChange={e => setCompletionUsd(e.target.value)} />
                </label>
              </div>

              <div className="agent-pricing" style={{ maxWidth: 360 }}>
                <div className="price-line"><span>Buyer pays per hire</span><span>{fmt$(totalCents)}</span></div>
                <div className="price-line"><span>Broker commission (10% of completion)</span><span>-{fmt$(commissionCents)}</span></div>
                <div className="price-line price-total"><span>You earn per hire</span><span>{fmt$(youKeepCents)}</span></div>
              </div>

              {error && <div className="market-note market-note-error">{error}</div>}

              <div>
                <button className="agent-hire" disabled={!valid || submitting} onClick={submit}>
                  {submitting ? 'Publishing…' : 'Publish to marketplace'}
                </button>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
