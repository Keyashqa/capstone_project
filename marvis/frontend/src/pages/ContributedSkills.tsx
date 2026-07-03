import { useEffect, useState } from 'react'
import Sidebar from '../components/Sidebar'
import { apiGetContributedSkills, type ContributedSkill } from '../api'

interface Props {
  email: string
  token: string
  onNavigate: (page: 'chat' | 'wallet' | 'marketplace' | 'owned-skills' | 'platform' | 'sell' | 'contributed') => void
  onLogout: () => void
}

const fmt$ = (c: number) => `$${(c / 100).toFixed(2)}`

const CONTRIB_ACCENTS = ['#1A73E8', '#137333', '#9334E6', '#B06000']
const accentFor = (seed: string) => {
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0
  return CONTRIB_ACCENTS[h % CONTRIB_ACCENTS.length]
}

export default function ContributedSkills({ email, token, onNavigate, onLogout }: Props) {
  const [skills, setSkills] = useState<ContributedSkill[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    apiGetContributedSkills(token)
      .then(setSkills)
      .catch(() => setError('Could not reach Marvis (is it running on :8000?)'))
      .finally(() => setLoading(false))
  }, [token])

  const totalEarned = skills.reduce((sum, s) => sum + s.earned_cents, 0)
  const totalHires = skills.reduce((sum, s) => sum + s.hires, 0)

  return (
    <div className="app-shell">
      <Sidebar
        active="contributed"
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
                <span className="eyebrow">Contributed Skills</span>
                <h1>Skills you've listed to the marketplace</h1>
                <p className="market-hero-sub">
                  Every skill you've published or promoted for others to hire — whether from{' '}
                  <b>Sell a Skill</b> or a Phase 2 build you chose to list. Earnings from these
                  land directly in your <b>MPay</b> wallet.
                </p>
              </div>
              <div className="market-stats">
                <div className="market-stat">
                  <div className="market-stat-num">{loading ? '—' : skills.length}</div>
                  <div className="market-stat-label">Listed</div>
                </div>
                <div className="market-stat">
                  <div className="market-stat-num">{loading ? '—' : totalHires}</div>
                  <div className="market-stat-label">Hires</div>
                </div>
                <div className="market-stat">
                  <div className="market-stat-num">{loading ? '—' : fmt$(totalEarned)}</div>
                  <div className="market-stat-label">Total earned</div>
                </div>
              </div>
            </div>
          </div>

          {loading ? (
            <div className="market-note">Loading contributed skills…</div>
          ) : error ? (
            <div className="market-note market-note-error">{error}</div>
          ) : skills.length === 0 ? (
            <div className="market-note">
              You haven't listed any skills yet. Head to <b>Sell a Skill</b> to publish one —
              once someone else hires it, it'll show up here with your earnings.
            </div>
          ) : (
            <div className="owned-grid">
              {skills.map(s => {
                const accent = accentFor(s.agent_name)
                const total = s.base_fee_cents + s.completion_fee_cents
                return (
                  <div
                    className="owned-card"
                    key={s.skill_id}
                    style={{ ['--accent' as any]: accent, cursor: 'default' }}
                  >
                    <div className="owned-card-top">
                      <div className="owned-avatar" style={{ background: accent }}>
                        {s.display_name.charAt(0).toUpperCase()}
                      </div>
                      <div className="owned-id">
                        <div className="owned-name">{s.display_name}</div>
                        <div className="owned-handle">@{s.agent_name}</div>
                      </div>
                      <span className="owned-badge">{s.hires} hire{s.hires === 1 ? '' : 's'}</span>
                    </div>
                    <p className="owned-desc">{s.description}</p>
                    {s.match_keywords.length > 0 && (
                      <div className="agent-tags" style={{ marginBottom: '.5rem' }}>
                        {s.match_keywords.slice(0, 4).map(k => <span className="agent-tag" key={k}>{k}</span>)}
                      </div>
                    )}
                    <div className="agent-pricing">
                      <div className="price-line"><span>Base + completion</span><span>{fmt$(total)}</span></div>
                      <div className="price-line price-total"><span>Total earned</span><span>{fmt$(s.earned_cents)}</span></div>
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
