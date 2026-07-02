import { useEffect, useRef, useState, type ReactNode } from 'react'
import {
  apiCreateAdkSession, apiVerifyPin, streamAdkRun,
  type AuthState, type HitlRequest, type Message, type A2uiSurface,
} from '../api'
import A2uiRenderer from '../components/A2uiRenderer'
import Sidebar, { BrandMark } from '../components/Sidebar'

interface Props {
  auth: AuthState
  onNavigate: (page: 'chat' | 'wallet' | 'marketplace' | 'owned-skills' | 'platform' | 'sell') => void
  onLogout: () => void
  onBalanceChange?: (cents: number) => void
}

const uid = () => Math.random().toString(36).slice(2)

const SUGGESTIONS = [
  'Write a tweet about my Marvis launch and save it as a Google Doc',
  'Draft a short product update post',
  'Summarize a document for me',
]

// ── Workflow activity feed ──────────────────────────────────
function statusMeta(raw: string): { icon: string; tone: 'ok' | 'default' | 'error' } {
  const t = raw.toLowerCase()
  if (/(failed|invalid|denied|cancelled|canceled|error|warning|timed out|could not|no specialist)/.test(t))
    return { icon: '⚠️', tone: 'error' }
  if (t.includes('pin confirmed')) return { icon: '🔐', tone: 'ok' }
  if (t.includes('checkout created')) return { icon: '🧾', tone: 'default' }
  if (t.includes('cartmandate verified')) return { icon: '🛡️', tone: 'ok' }
  if (t.includes('moved to escrow')) return { icon: '🔒', tone: 'default' }
  if (t.includes('grant')) return { icon: '🔑', tone: 'default' }
  if (t.includes('completed the task')) return { icon: '✅', tone: 'ok' }
  if (t.includes('released to agent') || t.includes('payout')) return { icon: '💸', tone: 'ok' }
  if (t.includes('escrow settled')) return { icon: '🤝', tone: 'ok' }
  if (t.includes('verification') || t.includes('checks') || t.includes('advisory')) return { icon: '🔍', tone: 'default' }
  if (t.includes('found') && t.includes('specialist')) return { icon: '🔎', tone: 'default' }
  return { icon: '•', tone: 'default' }
}

// Highlight id-like tokens (bkg-…, txn-…, grant-…, escrow:…) as chips
function highlightIds(text: string, keyPrefix: string): ReactNode[] {
  const re = /([a-z][a-z0-9]*[-:][0-9a-f]{6,})/gi
  const out: ReactNode[] = []
  let last = 0, i = 0, m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index))
    out.push(<code key={`${keyPrefix}-${i++}`} className="status-chip">{m[0]}</code>)
    last = m.index + m[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

function StatusFeed({ statuses }: { statuses: string[] }) {
  return (
    <div className="status-feed">
      <div className="status-feed-head"><span className="status-feed-pulse" /> Marvis activity</div>
      {statuses.map((raw, idx) => {
        const { icon, tone } = statusMeta(raw)
        const lines = raw.split('\n').map(l => l.trimEnd()).filter(l => l.trim() !== '')
        const [title, ...rest] = lines
        const last = idx === statuses.length - 1
        return (
          <div key={idx} className={`status-row status-${tone}${last ? ' status-row-last' : ''}`}>
            <span className="status-dot">{icon}</span>
            <div className="status-body">
              <div className="status-title">{highlightIds(title ?? '', `t${idx}`)}</div>
              {rest.map((l, i) => (
                <div key={i} className="status-detail">{highlightIds(l, `d${idx}-${i}`)}</div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function Chat({ auth, onNavigate, onLogout }: Props) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [busy, setBusy] = useState(false)
  const [hitl, setHitl] = useState<HitlRequest | null>(null)
  const [pinLoading, setPinLoading] = useState(false)
  const [input, setInput] = useState('')

  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { initSession() }, [])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const addMsg = (role: Message['role'], text: string) =>
    setMessages(prev => [...prev, { id: uid(), role, text }])

  const appendToLast = (text: string) => {
    setMessages(prev => {
      if (prev.length === 0) return prev
      const last = prev[prev.length - 1]
      if (last.role !== 'agent' || last.a2ui) return [...prev, { id: uid(), role: 'agent' as const, text }]
      return [...prev.slice(0, -1), { ...last, text: last.text + text }]
    })
  }

  const runStream = async (parts: object[], explicitSid?: string) => {
    const sid = explicitSid ?? sessionId
    if (!sid) return
    setBusy(true)
    let agentMsgStarted = false
    let receivedHitl = false
    try {
      for await (const ev of streamAdkRun(auth.userId, sid, parts)) {
        if (ev.a2ui) {
          setMessages(prev => [...prev, { id: uid(), role: 'agent', text: '', a2ui: ev.a2ui as A2uiSurface[] }])
          agentMsgStarted = false
        }
        if (ev.status) {
          const s = ev.status
          setMessages(prev => {
            const last = prev[prev.length - 1]
            if (last && last.role === 'agent' && last.statuses) {
              return [...prev.slice(0, -1), { ...last, statuses: [...last.statuses, s] }]
            }
            return [...prev, { id: uid(), role: 'agent', text: '', statuses: [s] }]
          })
          agentMsgStarted = false
        }
        if (ev.text) {
          if (!agentMsgStarted) {
            agentMsgStarted = true
            setMessages(prev => [...prev, { id: uid(), role: 'agent', text: ev.text! }])
          } else {
            appendToLast(ev.text)
          }
        }
        if (ev.hitl) {
          receivedHitl = true
          setHitl(ev.hitl)
          setBusy(false)  // Always unblock when hitl arrives — the card handles interaction
        }
        if (ev.done && !receivedHitl) setBusy(false)
      }
    } catch (err) {
      addMsg('system', `Error: ${err instanceof Error ? err.message : String(err)}`)
      setBusy(false)
    }
  }

  const initSession = async () => {
    try {
      const sid = await apiCreateAdkSession(auth.token)
      setSessionId(sid)
      addMsg('agent', 'Hi! I\'m Marvis, your personal AI orchestrator. Tell me what you\'d like to create today — for example: "Write a tweet about my Marvis launch and save it as a Twitter script in Google Docs."')
      setBusy(false)
    } catch {
      addMsg('system', 'Failed to connect to Marvis server (port 8000). Is the agent running?')
      setBusy(false)
    }
  }

  const sendGoal = async (override?: string) => {
    const goal = (override ?? input).trim()
    if (!goal || busy || !sessionId) return
    setInput('')
    addMsg('user', goal)
    await runStream([{ text: goal }])
  }

  // Called by A2uiRenderer when a button fires an event
  const handleA2uiEvent = async (eventName: string, context: Record<string, any>) => {
    if (!hitl || !sessionId || pinLoading) return

    if (eventName === 'decision') {
      const { decision, pin } = context

      if (decision === 'approve') {
        setPinLoading(true)
        const ok = await apiVerifyPin(auth.token, String(pin ?? ''), sessionId, hitl.interruptId)
        setPinLoading(false)

        if (!ok) {
          addMsg('system', 'Incorrect PIN. Try again.')
          return  // hitl stays set — card remains interactive
        }

        const capturedHitl = hitl
        setHitl(null)
        await runStream([{
          functionResponse: {
            id: capturedHitl.interruptId,
            name: 'adk_request_input',
            response: { result: 'confirmed' },
          },
        }])
      } else {
        // reject / cancel
        const capturedHitl = hitl
        setHitl(null)
        addMsg('system', 'Cancelled.')
        runStream([{
          functionResponse: {
            id: capturedHitl.interruptId,
            name: 'adk_request_input',
            response: { result: 'cancelled' },
          },
        }])
      }
    }
  }

  const showSuggestions = messages.length <= 1 && !busy && !hitl

  return (
    <div className="app-shell">
      <Sidebar
        active="chat"
        email={auth.email}
        balanceCents={auth.balanceCents}
        onNavigate={onNavigate}
        onLogout={onLogout}
      />

      <div className="chat-main">
      <div className="messages">
        <div className="messages-inner">
          {messages.map(m => {
            if (m.role === 'system') {
              return <div key={m.id} className="msg-system">{m.text}</div>
            }
            return (
              <div key={m.id} className={`msg-row msg-row-${m.role}`}>
                {m.role === 'agent' && (
                  <span className="msg-avatar"><BrandMark size={26} /></span>
                )}
                {m.statuses
                  ? <StatusFeed statuses={m.statuses} />
                  : (
                    <div className={`msg msg-${m.role}${m.a2ui ? ' msg-a2ui' : ''}`}>
                      {m.a2ui
                        ? (
                          <A2uiRenderer
                            surfaces={m.a2ui}
                            onEvent={handleA2uiEvent}
                            disabled={!hitl}
                            loading={pinLoading}
                          />
                        )
                        : m.text}
                    </div>
                  )}
              </div>
            )
          })}
          {busy && (
            <div className="msg-row msg-row-agent">
              <span className="msg-avatar"><BrandMark size={26} /></span>
              <div className="msg msg-agent">
                <div className="typing"><span /><span /><span /></div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="composer">
        <div className="composer-inner">
          {showSuggestions && (
            <div className="suggestions">
              {SUGGESTIONS.map(s => (
                <button key={s} className="suggestion-chip" onClick={() => sendGoal(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}
          <div className="chat-input-row">
            <input
              className="chat-input"
              type="text"
              placeholder="Describe your task…  e.g. Write a tweet about my Marvis launch"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendGoal()}
              disabled={busy || !!hitl}
            />
            <button
              className="btn-send"
              onClick={() => sendGoal()}
              disabled={busy || !!hitl || !input.trim()}
              aria-label="Send"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
                <path d="M4 12l15-7-5 15-3-6-7-2z" stroke="currentColor" strokeWidth="2"
                  strokeLinejoin="round" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        </div>
      </div>
      </div>
    </div>
  )
}
