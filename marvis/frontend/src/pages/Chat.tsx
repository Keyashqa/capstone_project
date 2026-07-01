import { useEffect, useRef, useState } from 'react'
import {
  apiCreateAdkSession, apiVerifyPin, streamAdkRun,
  type AuthState, type HitlRequest, type Message, type A2uiSurface,
} from '../api'
import A2uiRenderer from '../components/A2uiRenderer'

interface Props {
  auth: AuthState
  onNavigate: (page: 'wallet') => void
  onLogout: () => void
  onBalanceChange?: (cents: number) => void
}

const uid = () => Math.random().toString(36).slice(2)

// Interrupt IDs that require PIN modal
const PIN_INTERRUPTS = new Set(['payment_auth', 'payout_auth'])

export default function Chat({ auth, onNavigate, onLogout }: Props) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [busy, setBusy] = useState(false)
  const [hitl, setHitl] = useState<HitlRequest | null>(null)
  const [input, setInput] = useState('')

  const [pinValue, setPinValue] = useState('')
  const [pinError, setPinError] = useState('')
  const [pinLoading, setPinLoading] = useState(false)

  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { initSession() }, [])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const addMsg = (role: Message['role'], text: string) => {
    setMessages(prev => [...prev, { id: uid(), role, text }])
  }

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
          if (!PIN_INTERRUPTS.has(ev.hitl.interruptId)) setBusy(false)
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

  const sendGoal = async () => {
    const goal = input.trim()
    if (!goal || busy || !sessionId) return
    setInput('')
    addMsg('user', goal)
    await runStream([{ text: goal }])
  }

  const submitPin = async () => {
    if (!hitl || !sessionId) return
    setPinError('')
    setPinLoading(true)
    try {
      const ok = await apiVerifyPin(auth.token, pinValue, sessionId, hitl.interruptId)
      if (!ok) {
        setPinError('Incorrect PIN. Try again.')
        setPinLoading(false)
        return
      }
      const capturedHitl = hitl
      setHitl(null)
      setPinValue('')
      setPinLoading(false)
      await runStream([{
        functionResponse: {
          id: capturedHitl.interruptId,
          name: 'adk_request_input',
          response: { result: 'confirmed' },
        },
      }])
    } catch {
      setPinError('Verification failed. Try again.')
      setPinLoading(false)
    }
  }

  const cancelPin = () => {
    const capturedHitl = hitl
    setHitl(null)
    setPinValue('')
    setPinError('')
    setBusy(false)
    addMsg('system', 'Payment cancelled.')
    if (sessionId && capturedHitl) {
      runStream([{
        functionResponse: {
          id: capturedHitl.interruptId,
          name: 'adk_request_input',
          response: { result: 'cancelled' },
        },
      }])
    }
  }

  const handleA2uiAction = (actionName: string) => {
    if (!hitl || busy) return
    const h = hitl
    setHitl(null)
    runStream([{
      functionResponse: {
        id: h.interruptId,
        name: 'adk_request_input',
        response: { result: actionName },
      },
    }])
  }

  const fmt$ = (c: number) => `$${(c / 100).toFixed(2)}`
  const isPinModal = hitl && PIN_INTERRUPTS.has(hitl.interruptId)
  const pinLabel = hitl?.interruptId === 'payout_auth' ? 'Approve Payout' : 'Confirm Hire'

  return (
    <div className="chat-layout">
      {isPinModal && (
        <div className="modal-overlay">
          <div className="modal-card">
            <h2>🔐 {pinLabel}</h2>
            <p>Enter your PIN to {hitl?.interruptId === 'payout_auth' ? 'approve payout to specialist' : 'authorise this hire'}</p>
            <input
              className="pin-input"
              type="password" inputMode="numeric" maxLength={6}
              value={pinValue} onChange={e => setPinValue(e.target.value)}
              autoFocus
              onKeyDown={e => e.key === 'Enter' && submitPin()}
            />
            {pinError && <p className="error-msg">{pinError}</p>}
            <div className="modal-actions">
              <button className="btn-cancel" onClick={cancelPin}>Cancel</button>
              <button className="btn-confirm" onClick={submitPin} disabled={pinLoading || pinValue.length < 4}>
                {pinLoading ? 'Verifying…' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="chat-topbar">
        <h2>🤖 Marvis</h2>
        <div className="nav-links">
          <span className="wallet-badge" onClick={() => onNavigate('wallet')}>
            💳 {fmt$(auth.balanceCents)}
          </span>
          <button className="btn-secondary" onClick={() => onNavigate('wallet')}>Wallet</button>
          <button className="btn-secondary" onClick={onLogout}>Sign Out</button>
        </div>
      </div>

      <div className="messages">
        {messages.map(m => (
          <div key={m.id} className={`msg msg-${m.role}${m.a2ui ? ' msg-a2ui' : ''}`}>
            {m.a2ui
              ? <A2uiRenderer surfaces={m.a2ui} onAction={handleA2uiAction} disabled={busy} />
              : m.text}
          </div>
        ))}
        {busy && (
          <div className="msg msg-agent">
            <div className="typing"><span /><span /><span /></div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-row">
        <input
          className="chat-input"
          type="text"
          placeholder="Describe your task… e.g. Write a tweet about my Marvis launch"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendGoal()}
          disabled={busy || !!hitl}
        />
        <button className="btn-send" onClick={sendGoal} disabled={busy || !!hitl || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  )
}
