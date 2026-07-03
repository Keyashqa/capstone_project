import { useEffect, useMemo, useState } from 'react'
import Sidebar from '../components/Sidebar'
import BrandWord from '../components/BrandWord'
import Modal from '../components/Modal'
import { apiGetAgents, type MarketAgent } from '../api'

interface Props {
  email: string
  token: string
  onNavigate: (page: 'chat' | 'wallet' | 'marketplace' | 'owned-skills' | 'platform' | 'sell' | 'contributed' | 'about') => void
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
  { icon: '🛍️', title: 'Browse niche skills' },
  { icon: '💬', title: 'Describe your task' },
  { icon: '🤝', title: 'Marvis hires the match' },
  { icon: '✅', title: 'Pay for verified work' },
]

export default function Marketplace({ email, token, onNavigate, onLogout }: Props) {
  const [agents, setAgents] = useState<MarketAgent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [specialty, setSpecialty] = useState<string | null>(null)
  const [selected, setSelected] = useState<MarketAgent | null>(null)

  useEffect(() => {
    apiGetAgents()
      .then(setAgents)
      .catch(() => setError('Could not reach the marketplace (is Marvis running on :8000?)'))
      .finally(() => setLoading(false))
  }, [])

  const specialties = useMemo(() => {
    const counts = new Map<string, number>()
    agents.forEach(a => a.specialties.forEach(x => counts.set(x, (counts.get(x) ?? 0) + 1)))
    // Most common first, capped — a wall of 20 filter chips isn't a filter, it's noise.
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .slice(0, 6)
      .map(([name]) => name)
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
        token={token}
        onNavigate={onNavigate}
        onLogout={onLogout}
      />

      <div className="wallet-main">
        <main className="market-main">
          {/* ── Storyboard header ── */}
          <div className="market-hero">
            <div className="market-hero-top">
              <div>
                <span className="eyebrow">Skills <BrandWord text="Marketplace" /></span>
                <h1>The right voice for every post</h1>
              </div>
              <div className="market-stats">
                <div className="market-stat">
                  <div className="market-stat-num">{loading ? '—' : agents.length}</div>
                  <div className="market-stat-label">Total Skills</div>
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
                placeholder="Search by platform, task, or niche…"
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
            <div className="market-note">
              No niche skill matches that yet. Try a different platform or task — or just ask in Chat,
              and Marvis will commission one to fit.
            </div>
          ) : (
            <div className="owned-grid">
              {filtered.map(a => {
                const { emoji, accent } = look(a.agent_name)
                const total = a.base_fee_cents + a.completion_fee_cents
                return (
                  <button
                    className="owned-card glass-accent"
                    key={a.skill_id}
                    style={{ ['--accent' as any]: accent }}
                    onClick={() => setSelected(a)}
                  >
                    <div className="owned-card-top">
                      <div className="owned-avatar" style={{ background: accent }}>{emoji}</div>
                      <div className="owned-id">
                        <div className="owned-name">{a.display_name}</div>
                      </div>
                    </div>
                    <p className="owned-desc">{a.description}</p>
                    {a.specialties.length > 0 && (
                      <div className="agent-tags" style={{ marginBottom: '.5rem' }}>
                        {a.specialties.slice(0, 3).map(sp => (
                          <span className="agent-tag" key={sp}>{sp}</span>
                        ))}
                        {a.specialties.length > 3 && (
                          <span className="owned-tag-count">+{a.specialties.length - 3}</span>
                        )}
                      </div>
                    )}
                    <div className="owned-foot">
                      <span className="owned-price-mini">{fmt$(total)} / task</span>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </main>
      </div>

      {selected && (
        <Modal onClose={() => setSelected(null)}>
          <div className="owned-detail" style={{ ['--accent' as any]: look(selected.agent_name).accent }}>
            <div className="owned-detail-top">
              <div className="owned-avatar owned-avatar-lg" style={{ background: look(selected.agent_name).accent }}>
                {look(selected.agent_name).emoji}
              </div>
              <div>
                <div className="owned-detail-name">{selected.display_name}</div>
              </div>
            </div>

            <p className="owned-detail-desc">{selected.description}</p>

            {selected.specialties.length > 0 && (
              <div className="owned-detail-tags">
                {selected.specialties.slice(0, 6).map(sp => (
                  <span className="agent-tag" key={sp}>{sp}</span>
                ))}
                {selected.specialties.length > 6 && (
                  <span className="owned-tag-count">+{selected.specialties.length - 6} more</span>
                )}
              </div>
            )}

            <div className="agent-cap owned-detail-cap">
              <span className="agent-cap-icon">🔒</span>
              <div>
                <div className="agent-cap-title">Scoped capability</div>
                {selected.capabilities.map(c => (
                  <div className="agent-cap-tool" key={c.tool_name}>
                    <code>{c.mcp_server}.{c.tool_name}</code> — {c.why}
                  </div>
                ))}
                {selected.capabilities.length === 0 && (
                  <div className="agent-cap-tool">No MCP tool — this skill only generates text.</div>
                )}
              </div>
            </div>

            <div className="agent-pricing">
              <div className="price-line">
                <span>Base fee <em>(non-refundable)</em></span>
                <span>{fmt$(selected.base_fee_cents)}</span>
              </div>
              <div className="price-line">
                <span>On delivery <em>(refundable)</em></span>
                <span>{fmt$(selected.completion_fee_cents)}</span>
              </div>
              <div className="price-line price-total">
                <span>Total per task</span>
                <span>{fmt$(selected.base_fee_cents + selected.completion_fee_cents)}</span>
              </div>
            </div>

            <div className="owned-detail-foot" style={{ justifyContent: 'flex-end' }}>
              <button className="agent-hire" onClick={() => onNavigate('chat')}>
                Hire via Chat
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
