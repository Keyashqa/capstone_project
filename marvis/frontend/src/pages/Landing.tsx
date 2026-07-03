import { BrandMark } from '../components/Sidebar'
import BrandWord from '../components/BrandWord'
import Icon, { type IconName } from '../components/Icon'

interface Props {
  onGetStarted: () => void
  onSignIn: () => void
}

function MPayWordmark() {
  return <BrandWord text="MPay" />
}

const FEATURES: { icon: IconName; title: string; body: string }[] = [
  {
    icon: 'chat',
    title: 'Just describe your goal',
    body: 'No prompt engineering, no tools to wire up. Chat with Marvis in plain English and it figures out the rest.',
  },
  {
    icon: 'bolt',
    title: 'Marvis hires the right niche skill',
    body: 'From a marketplace of niche writing skills — each tuned to a platform, task, and voice — Marvis picks the best fit for your job.',
  },
  {
    icon: 'shieldCheck',
    title: 'Only pay for verified work',
    body: 'Every deliverable is checked before money moves. MPay holds funds in escrow until the work actually passes.',
  },
]

const STEPS = [
  { n: 1, title: 'Tell Marvis what you need', body: '“Write a launch tweet and save it to Google Docs.”' },
  { n: 2, title: 'Marvis hires a skill', body: 'It selects and briefs the right skill from the marketplace.' },
  { n: 3, title: 'The skill does the work', body: 'The task runs with only the permissions it actually needs.' },
  { n: 4, title: 'Verify, then pay with MPay', body: 'Marvis checks the result and releases payment on your OK.' },
]

const MPAY_FLOW: { icon: IconName; title: string; body: string; tag: string | null }[] = [
  { icon: 'wallet', title: 'Top up', body: 'Add funds to your MPay wallet.', tag: 'MPay' },
  { icon: 'cart', title: 'Hire & quote', body: 'Marvis gets a signed CartMandate — a tamper-proof quote — from the marketplace.', tag: 'UCP' },
  { icon: 'lock', title: 'Authorize & escrow', body: 'Your PIN signs a PaymentMandate (SD-JWT); MPay locks the funds in escrow.', tag: 'AP2' },
  { icon: 'gear', title: 'Work & verify', body: 'The hired skill does the job; Marvis verifies the result.', tag: null },
  { icon: 'swap', title: 'Settle', body: 'Passes → the skill is paid. Fails → you’re refunded.', tag: 'MPay' },
]

const PROTOCOLS = [
  {
    tag: 'UCP',
    cls: 'ucp',
    name: 'Universal Commerce Protocol',
    body:
      'The marketplace layer. Built on MCP, UCP is how Marvis discovers skills and hires them. ' +
      'Before any work starts, the broker returns a signed CartMandate — a tamper-proof quote describing exactly ' +
      'what you’ll get and what it costs.',
  },
  {
    tag: 'AP2',
    cls: 'ap2',
    name: 'Agent Payment Protocol',
    body:
      'The payment layer that powers MPay. AP2 uses two signed mandates — the CartMandate (what you agreed to) and ' +
      'a PaymentMandate issued as an SD-JWT (your authorization). Together they make every payment cryptographically ' +
      'provable and impossible to forge.',
  },
]

const STACK = [
  { label: 'Marvis', sub: 'Orchestration — the agent you talk to', cls: 'stack-marvis' },
  { label: 'MPay', sub: 'Wallet & settlement — what you see', cls: 'stack-mpay' },
  { label: 'AP2', sub: 'Payment authorization — signed mandates', cls: 'stack-ap2' },
  { label: 'UCP', sub: 'Skill marketplace & checkout', cls: 'stack-ucp' },
  { label: 'MCP', sub: 'Secure tool transport', cls: 'stack-mcp' },
]

export default function Landing({ onGetStarted, onSignIn }: Props) {
  return (
    <div className="landing">
      {/* ── Nav ── */}
      <header className="landing-nav">
        <div className="landing-nav-inner">
          <div className="brand">
            <BrandMark />
            <span className="brand-name"><BrandWord text="Marvis" /></span>
          </div>
          <div className="landing-nav-actions">
            <button className="nav-ghost" onClick={onSignIn}>Sign in</button>
            <button className="nav-cta" onClick={onGetStarted}>Get started</button>
          </div>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="hero">
        <div className="hero-copy">
          <span className="hero-badge"><Icon name="sparkle" size={15} /> A marketplace of niche AI ghostwriters</span>
          <h1>Tell Marvis what you need.<br />It gets it written.</h1>
          <p className="hero-sub">
            Marvis is a marketplace of niche writing skills — each in a creator's own voice. Describe your
            goal and Marvis hires the right one, verifies the work, and pays through <MPayWordmark /> only
            when it passes.
          </p>
          <div className="hero-cta">
            <button className="btn-hero" onClick={onGetStarted}>Get started free</button>
            <button className="btn-hero-ghost" onClick={onSignIn}>I already have an account</button>
          </div>
          <div className="hero-trust">
            <span><Icon name="lock" size={15} /> Escrow-backed payments</span>
            <span className="hero-trust-sep">·</span>
            <span><Icon name="shieldCheck" size={15} /> Verified deliverables</span>
            <span className="hero-trust-sep">·</span>
            <span><Icon name="bolt" size={15} /> Runs on your terms</span>
          </div>
        </div>

        {/* Chat mockup */}
        <div className="hero-visual" aria-hidden>
          <div className="mock-window">
            <div className="mock-bar">
              <span className="mock-dot" /><span className="mock-dot" /><span className="mock-dot" />
              <span className="mock-title"><BrandMark size={18} /> Marvis</span>
            </div>
            <div className="mock-body">
              <div className="mock-row mock-row-user">
                <div className="mock-msg mock-user">Write a tweet about my launch and save it to Google Docs.</div>
              </div>
              <div className="mock-row mock-row-agent">
                <span className="mock-avatar"><BrandMark size={20} /></span>
                <div className="mock-msg mock-agent">On it — hiring <b>DocWriter</b> for this task. I’ll verify the draft before any payment.</div>
              </div>
              <div className="mock-row mock-row-agent">
                <span className="mock-avatar" style={{ visibility: 'hidden' }}><BrandMark size={20} /></span>
                <div className="mock-pay">
                  <div className="mock-pay-head"><MPayWordmark /> · confirm payment</div>
                  <div className="mock-pay-amt">$2.00</div>
                  <div className="mock-pay-sub">Held in escrow · released on verification</div>
                  <div className="mock-pay-btns">
                    <span className="mock-pin">••••</span>
                    <span className="mock-pay-approve">Approve</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── What is Marvis ── */}
      <section className="section" id="what">
        <div className="section-head">
          <span className="eyebrow">What is Marvis</span>
          <h2>An orchestrator, not just another chatbot</h2>
          <p className="section-sub">
            Marvis is the layer between you and a marketplace of niche writing skills. It understands your
            goal, hires the right skill, supervises the work, and settles payment — and creators earn every
            time their skill is hired.
          </p>
        </div>
        <div className="feature-grid">
          {FEATURES.map(f => (
            <div className="feature-card" key={f.title}>
              <div className="feature-icon"><Icon name={f.icon} size={24} /></div>
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="section section-alt" id="how">
        <div className="section-head">
          <span className="eyebrow">How you get work done</span>
          <h2>From a sentence to a finished deliverable</h2>
        </div>
        <div className="steps">
          {STEPS.map((s, i) => (
            <div className="step" key={s.n}>
              <div className="step-num">{s.n}</div>
              <div className="step-text">
                <h4>{s.title}</h4>
                <p>{s.body}</p>
              </div>
              {i < STEPS.length - 1 && <div className="step-line" />}
            </div>
          ))}
        </div>
      </section>

      {/* ── MPay ── */}
      <section className="section mpay-section" id="mpay">
        <div className="section-head">
          <span className="eyebrow">Payments, handled</span>
          <h2>Meet <MPayWordmark /> — payments you can trust</h2>
          <p className="section-sub">
            <MPayWordmark /> is the wallet and settlement layer built into Marvis. Under the hood it runs on the
            open <b>AP2</b> payment protocol and a double-entry ledger — so money only moves when the work is
            verified, and every payment is signed by your PIN.
          </p>
        </div>

        <div className="mpay-flow">
          {MPAY_FLOW.map((step, i) => (
            <div className="flow-item" key={step.title}>
              <div className="flow-node">
                <div className="flow-icon"><Icon name={step.icon} size={24} /></div>
                <div className="flow-num">
                  Step {i + 1}
                  {step.tag && <span className={`flow-tag flow-tag-${step.tag.toLowerCase()}`}>{step.tag}</span>}
                </div>
                <h4>{step.title}</h4>
                <p>{step.body}</p>
              </div>
              {i < MPAY_FLOW.length - 1 && <div className="flow-arrow">→</div>}
            </div>
          ))}
        </div>

        <div className="mpay-ledger">
          <span className="ledger-dot" />
          Every transaction is double-entry — debits and credits always balance to <b>$0.00</b>.
          No money is created or lost, only moved.
        </div>
      </section>

      {/* ── Open protocols ── */}
      <section className="section section-alt" id="protocols">
        <div className="section-head">
          <span className="eyebrow">Under the hood</span>
          <h2>Open protocols, not a black box</h2>
          <p className="section-sub">
            Marvis doesn’t invent its own rails. Hiring runs on <b>UCP</b> and payments run on <b>AP2</b> —
            open, interoperable agent protocols — so every transaction is standard, auditable, and verifiable.
          </p>
        </div>

        <div className="protocol-grid">
          {PROTOCOLS.map(p => (
            <div className={`protocol-card protocol-${p.cls}`} key={p.tag}>
              <div className="protocol-head">
                <span className={`protocol-badge protocol-badge-${p.cls}`}>{p.tag}</span>
                <h3>{p.name}</h3>
              </div>
              <p>{p.body}</p>
            </div>
          ))}
        </div>

        <div className="stack">
          <div className="stack-caption">The Marvis stack</div>
          {STACK.map(layer => (
            <div className={`stack-layer ${layer.cls}`} key={layer.label}>
              <span className="stack-label">{layer.label}</span>
              <span className="stack-sub">{layer.sub}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ── Final CTA ── */}
      <section className="cta-band">
        <h2>Ready to put Marvis to work?</h2>
        <p>Create an account, top up your <MPayWordmark /> wallet, and hand off your first task in minutes.</p>
        <button className="btn-hero" onClick={onGetStarted}>Get started free</button>
      </section>

      <footer className="landing-footer">
        <div className="brand">
          <BrandMark size={22} />
          <span className="brand-name"><BrandWord text="Marvis" /></span>
        </div>
        <span className="footer-note">Marvis · powered by <MPayWordmark /> · a capstone project</span>
      </footer>
    </div>
  )
}
