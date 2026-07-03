import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import Modal from '../components/Modal'
import { apiGetOwnedSkills, type OwnedSkill } from '../api'

interface Props {
  email: string
  token: string
  onNavigate: (page: 'chat' | 'wallet' | 'marketplace' | 'owned-skills' | 'platform' | 'sell' | 'contributed' | 'about') => void
  onLogout: () => void
}

// A different accent family from the marketplace cards — these are Marvis's
// own, not rented, so they read visually as "owned" rather than "for hire".
const OWNED_ACCENTS = ['#137333', '#9334E6', '#B06000', '#1A73E8']
const accentFor = (seed: string) => {
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0
  return OWNED_ACCENTS[h % OWNED_ACCENTS.length]
}

export default function OwnedSkills({ email, token, onNavigate, onLogout }: Props) {
  const [skills, setSkills] = useState<OwnedSkill[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<OwnedSkill | null>(null)

  useEffect(() => {
    apiGetOwnedSkills()
      .then(setSkills)
      .catch(() => setError('Could not reach Marvis (is it running on :8000?)'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="app-shell">
      <Sidebar
        active="owned-skills"
        email={email}
        token={token}
        onNavigate={onNavigate}
        onLogout={onLogout}
      />

      <div className="wallet-main">
        <main className="market-main">
          <div className="market-hero">
            <div className="market-hero-top">
              <div>
                <span className="eyebrow">Owned Skills</span>
                <h1>Skills Marvis built for itself</h1>
              </div>
              <div className="market-stats">
                <div className="market-stat">
                  <div className="market-stat-num">{loading ? '—' : skills.length}</div>
                  <div className="market-stat-label">Total Owned</div>
                </div>
              </div>
            </div>
          </div>

          {loading ? (
            <div className="market-note">Loading owned skills…</div>
          ) : error ? (
            <div className="market-note market-note-error">{error}</div>
          ) : skills.length === 0 ? (
            <div className="market-note">
              No owned skills yet. Ask Marvis to do something no marketplace skill
              covers (e.g. a platform it hasn't built for) — it will commission one and
              it'll show up here for good.
            </div>
          ) : (
            <div className="owned-grid">
              {skills.map(s => {
                const accent = accentFor(s.agent_name)
                return (
                  <button
                    className="owned-card glass-accent"
                    key={s.skill_id}
                    style={{ ['--accent' as any]: accent }}
                    onClick={() => setSelected(s)}
                  >
                    <div className="owned-card-top">
                      <div className="owned-avatar" style={{ background: accent }}>
                        {s.display_name.charAt(0).toUpperCase()}
                      </div>
                      <div className="owned-id">
                        <div className="owned-name">{s.display_name}</div>
                      </div>
                    </div>
                    <p className="owned-desc">{s.description}</p>
                    <div className="owned-foot">
                      <span className="owned-price-mini">Free</span>
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
          <div className="owned-detail" style={{ ['--accent' as any]: accentFor(selected.agent_name) }}>
            <div className="owned-detail-top">
              <div className="owned-avatar owned-avatar-lg" style={{ background: accentFor(selected.agent_name) }}>
                {selected.display_name.charAt(0).toUpperCase()}
              </div>
              <div>
                <div className="owned-detail-name">{selected.display_name}</div>
              </div>
              <span className="owned-badge">Owned · Free</span>
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

            <div className="owned-detail-instruction">
              <div className="agent-cap-title">System instruction</div>
              <pre>{selected.instruction}</pre>
            </div>

            <div className="owned-detail-foot" style={{ justifyContent: 'flex-end' }}>
              <button className="agent-hire" onClick={() => onNavigate('chat')}>
                Use via Chat
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
