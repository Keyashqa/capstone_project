const AGENT = ''  // relative URLs — Vite proxy forwards to :8000, no CORS

export interface AuthState {
  token: string
  userId: string
  email: string
  balanceCents: number
}

export async function apiRegister(email: string, password: string, pin: string): Promise<AuthState> {
  const r = await fetch(`${AGENT}/auth/register`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, pin }),
  })
  if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Registration failed') }
  const d = await r.json()
  return { token: d.token, userId: d.user_id, email: d.email, balanceCents: d.balance_cents }
}

export async function apiLogin(email: string, password: string): Promise<AuthState> {
  const r = await fetch(`${AGENT}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Login failed') }
  const d = await r.json()
  return { token: d.token, userId: d.user_id, email: d.email, balanceCents: d.balance_cents }
}

export async function apiCreateAdkSession(token: string): Promise<string> {
  const r = await fetch(`${AGENT}/adk-sessions`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  })
  if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Session creation failed') }
  const d = await r.json()
  return d.adk_session_id
}

export async function apiVerifyPin(
  token: string,
  pin: string,
  adkSessionId: string,
  interruptId: string = 'payment_auth',
): Promise<boolean> {
  const r = await fetch(`${AGENT}/auth/verify-pin`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, pin, adk_session_id: adkSessionId, interrupt_id: interruptId }),
  })
  if (!r.ok) return false
  const d = await r.json()
  return d.ok === true
}

export async function apiGetWallet(token: string): Promise<{ balanceCents: number; transactions: Transaction[] }> {
  const r = await fetch(`${AGENT}/wallet/balance?token=${encodeURIComponent(token)}`)
  if (!r.ok) throw new Error('Failed to load wallet')
  const d = await r.json()
  return { balanceCents: d.balance_cents, transactions: d.transactions }
}

export async function apiTopup(token: string, amountCents: number): Promise<number> {
  const r = await fetch(`${AGENT}/wallet/topup`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, amount_cents: amountCents }),
  })
  if (!r.ok) throw new Error('Topup failed')
  const d = await r.json()
  return d.balance_cents
}

export interface AgentCapability {
  mcp_server: string
  tool_name: string
  why: string
}

export interface MarketAgent {
  skill_id: string
  agent_name: string
  display_name: string
  version: string
  description: string
  specialties: string[]
  model: string
  currency: string
  base_fee_cents: number
  completion_fee_cents: number
  capabilities: AgentCapability[]
  reputation: number | null
}

export async function apiGetAgents(): Promise<MarketAgent[]> {
  const r = await fetch(`${AGENT}/marketplace/agents`)
  if (!r.ok) throw new Error('Failed to load marketplace')
  const d = await r.json()
  return d.agents as MarketAgent[]
}

export interface OwnedSkill {
  skill_id: string
  agent_name: string
  display_name: string
  version: string
  description: string
  specialties: string[]
  model: string
  instruction: string
  capabilities: AgentCapability[]
}

export async function apiGetOwnedSkills(): Promise<OwnedSkill[]> {
  const r = await fetch(`${AGENT}/owned-skills`)
  if (!r.ok) throw new Error('Failed to load owned skills')
  const d = await r.json()
  return d.skills as OwnedSkill[]
}

export interface PlatformFeedEvent {
  journal_id: string
  to_account: string
  from_account: string
  amount_cents: number
  reason: string
  reference_id: string | null
  created_at: string
}

export interface PlatformAgentEarnings {
  agent_name: string
  earned_cents: number
}

export interface PlatformStats {
  total_volume_cents: number
  total_paid_to_agents_cents: number
  total_refunded_cents: number
  total_topped_up_cents: number
  hire_count: number
  per_agent: PlatformAgentEarnings[]
  feed: PlatformFeedEvent[]
}

export async function apiGetPlatformStats(): Promise<PlatformStats> {
  const r = await fetch(`${AGENT}/platform/stats`)
  if (!r.ok) throw new Error('Failed to load platform stats')
  return r.json()
}

export interface JobReceipt {
  task_id: string
  goal: string
  agent_name: string
  skill_id: string
  booking_id: string | null
  txn_id: string | null
  grant_id: string | null
  doc_id: string | null
  doc_url: string | null
  output: string
  tools: Array<string | { tool?: string; [k: string]: unknown }>
  verification: { advisory_score?: number; passed?: boolean; [k: string]: unknown }
  base_fee_cents: number
  completion_fee_cents: number
  total_cents: number
  status: string
  created_at: string
}

export interface Transaction {
  id: string
  delta_cents: number
  reason: string
  reference_id: string | null
  created_at: string
  job?: JobReceipt
}

export interface HitlRequest {
  interruptId: string
  question: string
}

export type A2uiTextValue =
  | string
  | { path: string }
  | { call: string; args: Record<string, any>; returnType?: string }

export interface A2uiComponent {
  id: string
  component: 'Column' | 'Row' | 'Card' | 'Text' | 'Divider' | 'Button' | 'TextField' | 'Icon'
  // layout
  children?: string[]
  child?: string
  align?: string
  justify?: string
  spacing?: number
  weight?: number
  style?: Record<string, string>
  // Text
  text?: A2uiTextValue
  variant?: string
  // TextField
  label?: string
  value?: { path: string }
  keyboardType?: string
  checks?: Array<{ condition: any; message: string }>
  // Icon
  name?: string
  // Button
  action?: { event: { name: string; context?: Record<string, any> } }
}

export interface A2uiSurface {
  version: string
  createSurface?: { surfaceId: string; catalogId: string }
  updateComponents?: { surfaceId: string; components: A2uiComponent[] }
  data?: Record<string, any>
}

export interface Message {
  id: string
  role: 'user' | 'agent' | 'system'
  text: string
  a2ui?: A2uiSurface[]
  statuses?: string[]
}

export async function* streamAdkRun(
  userId: string,
  sessionId: string,
  parts: object[],
): AsyncGenerator<{ text?: string; status?: string; hitl?: HitlRequest; a2ui?: A2uiSurface[]; done?: boolean }> {
  const body = JSON.stringify({
    app_name: 'app',
    user_id: userId,
    session_id: sessionId,
    streaming: true,
    new_message: { role: 'user', parts },
  })

  const resp = await fetch(`${AGENT}/run_sse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
  })

  if (!resp.ok || !resp.body) {
    throw new Error(`SSE failed: ${resp.status}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.startsWith('data:')) continue
      const raw = line.slice(5).trim()
      if (!raw || raw === '[DONE]') continue
      try {
        const ev = JSON.parse(raw)
        const evParts = ev?.content?.parts ?? []
        for (const p of evParts) {
          if (p.text) {
            const raw = p.text as string
            const m = raw.match(/<a2ui-json>([\s\S]*?)<\/a2ui-json>/)
            if (m) {
              try { yield { a2ui: JSON.parse(m[1]) as A2uiSurface[] } } catch { /* ignore */ }
            } else if (raw.includes('<mstat>')) {
              const re = /<mstat>([\s\S]*?)<\/mstat>/g
              let mm: RegExpExecArray | null
              while ((mm = re.exec(raw)) !== null) {
                const inner = mm[1].trim()
                if (inner) yield { status: inner }
              }
            } else {
              yield { text: raw }
            }
          }
          if (p.functionCall?.name === 'adk_request_input') {
            yield {
              hitl: {
                interruptId: p.functionCall.id ?? p.functionCall.args?.interrupt_id ?? 'unknown',
                question: p.functionCall.args?.question ?? '',
              },
            }
          }
        }
      } catch { /* ignore malformed */ }
    }
  }
  yield { done: true }
}
