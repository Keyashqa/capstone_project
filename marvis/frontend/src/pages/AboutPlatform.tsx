import Sidebar from '../components/Sidebar'
import Icon, { type IconName } from '../components/Icon'

type NavPage = 'chat' | 'wallet' | 'marketplace' | 'owned-skills' | 'platform' | 'sell' | 'contributed' | 'about'

interface Props {
  email: string
  token: string
  onNavigate: (page: NavPage) => void
  onLogout: () => void
}

// Inline brand marks — the app is offline / CSP-strict, so no remote logo assets.
function InstaLogo({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      <defs>
        <linearGradient id="ig-grad" x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#FEDA75" />
          <stop offset=".25" stopColor="#FA7E1E" />
          <stop offset=".5" stopColor="#D62976" />
          <stop offset=".75" stopColor="#962FBF" />
          <stop offset="1" stopColor="#4F5BD5" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="20" height="20" rx="5.5" fill="url(#ig-grad)" />
      <circle cx="12" cy="12" r="4.4" fill="none" stroke="#fff" strokeWidth="1.7" />
      <circle cx="17.2" cy="6.8" r="1.25" fill="#fff" />
    </svg>
  )
}

function LinkedInLogo({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      <rect x="2" y="2" width="20" height="20" rx="4" fill="#0A66C2" />
      <path
        fill="#fff"
        d="M7.2 9.6h2.15V17H7.2zM8.28 6.35a1.27 1.27 0 1 1 0 2.55 1.27 1.27 0 0 1 0-2.55zM10.9 9.6h2.06v1.01h.03c.29-.53 1-1.1 2.05-1.1 2.2 0 2.6 1.4 2.6 3.22V17h-2.15v-2.82c0-.67-.01-1.54-.94-1.54-.94 0-1.08.73-1.08 1.49V17H10.9z"
      />
    </svg>
  )
}

const PLATFORMS: { name: string; logo: React.ReactNode }[] = [
  { name: 'Instagram', logo: <InstaLogo /> },
  { name: 'LinkedIn', logo: <LinkedInLogo /> },
]
const TASKS = ['Product launch', 'Promotion']
const DOMAINS = ['Tech', 'Marketing', 'Management']

const BUYER_STEPS: { icon: IconName; title: string; body: string }[] = [
  { icon: 'chat', title: 'Describe your goal', body: 'Tell Marvis what you want written, in plain English — a launch tweet, a LinkedIn announcement, a Product Hunt blurb.' },
  { icon: 'search', title: 'Marvis hires the right niche skill', body: 'It matches your request to a specialist skill — the right platform, task, and voice — and books it for you.' },
  { icon: 'lock', title: 'You approve with your PIN', body: 'Nothing is paid until you authorize the hire. Your funds are held in escrow, not spent.' },
  { icon: 'shieldCheck', title: 'Verify, then pay', body: 'Marvis checks the delivered work against your brief. You only release payment for work that passes.' },
]

const CREATOR_STEPS: { icon: IconName; title: string; body: string }[] = [
  { icon: 'doc', title: 'List a skill in your voice', body: 'Write the instruction that captures your style for a specific platform, task, and niche.' },
  { icon: 'receipt', title: 'Set your price', body: 'Choose a base and a completion fee. The platform takes a small commission on each hire.' },
  { icon: 'cash', title: 'Earn on every hire', body: 'When someone hires your skill and the work is verified, your payout lands straight in your MPay wallet.' },
]

const SIDES: { icon: IconName; title: string; body: string; cta: string; page: NavPage }[] = [
  { icon: 'cart', title: 'Rent a skill', body: 'Hire a niche ghostwriter for a one-off job. Pay only for work that passes verification.', cta: 'Browse the marketplace', page: 'marketplace' },
  { icon: 'bolt', title: 'Build & own a skill', body: 'Ask for something no skill covers yet. Marvis commissions a builder, then keeps the skill — reusable and free to run again.', cta: 'See owned skills', page: 'owned-skills' },
  { icon: 'cash', title: 'List & earn', body: 'Publish your own-voice skill and earn a payout every time another user hires it.', cta: 'Contribute a skill', page: 'sell' },
]

export default function AboutPlatform({ email, token, onNavigate, onLogout }: Props) {
  return (
    <div className="app-shell">
      <Sidebar
        active="about"
        email={email}
        token={token}
        onNavigate={onNavigate}
        onLogout={onLogout}
      />

      <div className="wallet-main">
        <main className="market-main">
          {/* ── Hook ── */}
          <div className="market-hero about-hero">
            <h1>Describe it. Marvis finds the skill which nails it.</h1>
          </div>

          {/* ── Niche matrix ── */}
          <div className="about-matrix">
            <div className="about-matrix-col about-col-platform">
              <div className="about-matrix-head">Platform</div>
              <div className="about-matrix-items">
                {PLATFORMS.map(p => (
                  <span className="about-chip" key={p.name}>
                    <span className="about-chip-logo">{p.logo}</span>{p.name}
                  </span>
                ))}
              </div>
            </div>

            <span className="about-matrix-x">×</span>

            <div className="about-matrix-col about-col-task">
              <div className="about-matrix-head">Task</div>
              <div className="about-matrix-items">
                {TASKS.map(t => <span className="about-chip" key={t}>{t}</span>)}
              </div>
            </div>

            <span className="about-matrix-x">×</span>

            <div className="about-matrix-col about-col-domain">
              <div className="about-matrix-head">Domain</div>
              <div className="about-matrix-items">
                {DOMAINS.map(d => <span className="about-chip" key={d}>{d}</span>)}
              </div>
            </div>
          </div>

          {/* ── Combinatorial space ── */}
          <div className="about-combos">
            <div className="about-combos-formula">
              O(<span className="combo-m">M</span> × <span className="combo-n">N</span> × <span className="combo-l">L</span>)
            </div>
            <div className="about-combos-note">possible niche combinations — the catalog grows to fill them</div>
          </div>

          {/* ── Example prompt ── */}
          <div className="about-example">
            <span className="about-example-label">Example prompt</span>
            <div className="about-example-card">
              <span className="about-example-icon"><Icon name="chat" size={18} /></span>
              <span className="about-example-text">
                “Write a LinkedIn product launch post for my tech startup.”
              </span>
            </div>
          </div>

          {/* ── How it works — buyers ── */}
          <section className="about-block">
            <h2 className="about-h2">How it works — for buyers</h2>
            <ol className="about-steps">
              {BUYER_STEPS.map((s, i) => (
                <li className="about-step" key={s.title}>
                  <span className="about-step-num">{i + 1}</span>
                  <span className="about-step-icon"><Icon name={s.icon} size={18} /></span>
                  <div className="about-step-text">
                    <h4>{s.title}</h4>
                    <p>{s.body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          {/* ── How it works — creators ── */}
          <section className="about-block">
            <h2 className="about-h2">How it works — for creators</h2>
            <ol className="about-steps">
              {CREATOR_STEPS.map((s, i) => (
                <li className="about-step" key={s.title}>
                  <span className="about-step-num">{i + 1}</span>
                  <span className="about-step-icon"><Icon name={s.icon} size={18} /></span>
                  <div className="about-step-text">
                    <h4>{s.title}</h4>
                    <p>{s.body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          {/* ── Self-growing ── */}
          <div className="about-callout">
            <span className="about-callout-icon"><Icon name="sparkle" size={22} /></span>
            <div>
              <b>The marketplace expands to fit demand.</b> If someone needs a niche that doesn't exist
              yet, Marvis commissions a builder to create the skill on the spot, then completes the job.
              Every unmet request is a chance for the catalog to grow.
            </div>
          </div>

          {/* ── Three sides ── */}
          <section className="about-block">
            <h2 className="about-h2">Three ways to use Marvis</h2>
            <div className="feature-grid">
              {SIDES.map(s => (
                <div className="feature-card about-side" key={s.title}>
                  <div className="feature-icon"><Icon name={s.icon} size={24} /></div>
                  <h3>{s.title}</h3>
                  <p>{s.body}</p>
                  <button className="agent-hire about-side-cta" onClick={() => onNavigate(s.page)}>
                    {s.cta} →
                  </button>
                </div>
              ))}
            </div>
          </section>
        </main>
      </div>
    </div>
  )
}
