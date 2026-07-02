import { useEffect, useMemo, useState } from 'react'
import Sidebar from '../components/Sidebar'
import { apiGetAgents, type MarketAgent } from '../api'

interface Props {
  email: string
  balanceCents: number
  onNavigate: (page: 'chat' | 'wallet' | 'marketplace' | 'owned-skills' | 'platform' | 'sell') => void
  onLogout: () => void
}

const fmt$ = (c: number) => `$${(c / 100).toFixed(2)}`

// Visual identity per agent (falls back gracefully for new agents)
const AGENT_LOOKS: Record<string, { emoji: string; accent: string }> = {
  DocWriter: { emoji: '✍️', accent: '#1A73E8' },
  DocReader: { emoji: '📖', accent: '#137333' },
}
const look = (name: string) =>
  AGENT_LOOKS[name] ?? { emoji: '🤖', accent: '#6B3FD4' }

const STORYBOARD = [
  { icon: '🛍️', title: 'Browse specialists' },
  { icon: '💬', title: 'Describe your task' },
  { icon: '🤝', title: 'Marvis hires the match' },
  { icon: '✅', title: 'Pay on delivery' },
]

export default function Marketplace({ email, balanceCents, onNavigate, onLogout }: Props) {
  const [agents, setAgents] = useState<MarketAgent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [specialty, setSpecialty] = useState<string | null>(null)

  useEffect(() => {
    apiGetAgents()
      .then(setAgents)
      .catch(() => setError('Could not reach the marketplace (is Marvis running on :8000?)'))
      .finally(() => setLoading(false))
  }, [])

  const specialties = useMemo(() => {
    const s = new Set<string>()
    agents.forEach(a => a.specialties.forEach(x => s.add(x)))
    return Array.from(s).sort()
  }, [agents])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return agents.filter(a => {
      const matchesSpecialty = !specialty || a.specialties.includes(specialty)
      const matchesQuery =
        !q ||
        a.display_name.toLowerCase().includes(q) ||
        a.agent_name.toLowerCase().includes(q) ||
        a.description.toLowerCase().includes(q) ||
        a.specialties.some(s => s.toLowerCase().includes(q))
      return matchesSpecialty && matchesQuery
    })
  }, [agents, query, specialty])

  return (
    <div className="app-shell">
      <Sidebar
        active="marketplace"
        email={email}
        balanceCents={balanceCents}
        onNavigate={onNavigate}
        onLogout={onLogout}
      />

      <div className="wallet-main">
        <main className="market-main">
          {/* ── Storyboard header ── */}
          <div className="market-hero">
            <div className="market-hero-top">
              <div>
                <span className="eyebrow">Agent Marketplace</span>
                <h1>Specialists, ready to be hired</h1>
                <p className="market-hero-sub">
                  Browse the agents Marvis can put to work for you. Each one is scoped to
                  least-privilege access, priced upfront, and paid through <b>MPay</b> only after its
                  deliverable passes verification.
                </p>
              </div>
              <div className="market-stats">
                <div className="market-stat">
                  <div className="market-stat-num">{loading ? '—' : agents.length}</div>
                  <div className="market-stat-label">Agents</div>
                </div>
              </div>
            </div>

            <div className="storyboard">
              {STORYBOARD.map((s, i) => (
                <div className="story-step" key={s.title}>
                  <div className="story-icon">{s.icon}</div>
                  <div className="story-text">
                    <div className="story-num">Step {i + 1}</div>
                    <h4>{s.title}</h4>
                  </div>
                  {i < STORYBOARD.length - 1 && <span className="story-arrow">→</span>}
                </div>
              ))}
            </div>
          </div>

          {/* ── Toolbar ── */}
          <div className="market-toolbar">
            <div className="market-search">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden>
                <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.8" />
                <path d="M16.5 16.5L21 21" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
              <input
                placeholder="Search agents, skills, or tasks…"
                value={query}
                onChange={e => setQuery(e.target.value)}
              />
            </div>
            {specialties.length > 0 && (
              <div className="market-filters">
                <button
                  className={`filter-chip${!specialty ? ' filter-chip-active' : ''}`}
                  onClick={() => setSpecialty(null)}
                >
                  All
                </button>
                {specialties.map(s => (
                  <button
                    key={s}
                    className={`filter-chip${specialty === s ? ' filter-chip-active' : ''}`}
                    onClick={() => setSpecialty(specialty === s ? null : s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* ── Grid ── */}
          {loading ? (
            <div className="market-note">Loading marketplace…</div>
          ) : error ? (
            <div className="market-note market-note-error">{error}</div>
          ) : filtered.length === 0 ? (
            <div className="market-note">No agents match your search.</div>
          ) : (
            <div className="agent-grid">
              {filtered.map(a => {
                const { emoji, accent } = look(a.agent_name)
                const total = a.base_fee_cents + a.completion_fee_cents
                return (
                  <div className="agent-card" key={a.skill_id} style={{ ['--accent' as any]: accent }}>
                    <div className="agent-card-top">
                      <div className="agent-avatar" style={{ background: accent }}>{emoji}</div>
                      <div className="agent-id">
                        <div className="agent-name">
                          {a.display_name}
                          <span className="agent-verified" title="Cryptographically verified identity">✓</span>
                        </div>
                        <div className="agent-handle">@{a.agent_name}</div>
                      </div>
                      <div className="agent-rep" title="New to the marketplace">★ New</div>
                    </div>

                    <p className="agent-desc">{a.description}</p>

                    <div className="agent-tags">
                      {a.specialties.slice(0, 4).map(s => (
                        <span className="agent-tag" key={s}>{s}</span>
                      ))}
                    </div>

                    <div className="agent-cap">
                      <span className="agent-cap-icon">🔒</span>
                      <div>
                        <div className="agent-cap-title">Scoped capability</div>
                        {a.capabilities.map(c => (
                          <div className="agent-cap-tool" key={c.tool_name}>
                            <code>{c.mcp_server}.{c.tool_name}</code> — {c.why}
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="agent-pricing">
                      <div className="price-line">
                        <span>Base fee <em>(non-refundable)</em></span>
                        <span>{fmt$(a.base_fee_cents)}</span>
                      </div>
                      <div className="price-line">
                        <span>On delivery <em>(refundable)</em></span>
                        <span>{fmt$(a.completion_fee_cents)}</span>
                      </div>
                      <div className="price-line price-total">
                        <span>Total per task</span>
                        <span>{fmt$(total)}</span>
                      </div>
                    </div>

                    <div className="agent-foot">
                      <span className="agent-model">⚡ {a.model.replace('ollama/', '')}</span>
                      <button className="agent-hire" onClick={() => onNavigate('chat')}>
                        Hire via Chat
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
