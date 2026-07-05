import { useState } from 'react'
import type { A2uiSurface, A2uiComponent } from '../api'
import Icon, { type IconName } from './Icon'

interface Props {
  surfaces: A2uiSurface[]
  onEvent?: (eventName: string, context: Record<string, any>) => void
  disabled?: boolean
  loading?: boolean
}

export default function A2uiRenderer({ surfaces, onEvent, disabled, loading }: Props) {
  // Build component map from all surfaces
  const compMap = new Map<string, A2uiComponent>()
  let initialData: Record<string, any> = {}
  for (const surface of surfaces) {
    if (surface.updateComponents) {
      for (const comp of surface.updateComponents.components) {
        compMap.set(comp.id, comp)
      }
    }
    if (surface.data) initialData = { ...initialData, ...surface.data }
  }

  const [formData, setFormData] = useState<Record<string, any>>(initialData)

  const setField = (key: string, value: string) =>
    setFormData(prev => ({ ...prev, [key]: value }))

  // Resolve a value that may be a literal, a {path} ref, or a {call} expression
  const resolve = (ref: any): any => {
    if (ref === null || ref === undefined) return ''
    if (typeof ref !== 'object') return ref
    if (ref.path) {
      const key = String(ref.path).replace(/^\//, '')
      return formData[key] ?? ''
    }
    if (ref.call === 'formatCurrency') {
      const val = Number(resolve(ref.args?.value ?? 0))
      const cur = String(resolve(ref.args?.currency ?? '$'))
      return `${cur}${val.toFixed(2)}`
    }
    if (ref.call === 'formatString') {
      const template = String(ref.args?.value ?? '')
      return template.replace(/\{\/([^}]+)\}/g, (_, k) => String(formData[k] ?? ''))
    }
    if (ref.call === 'regex') {
      const val = String(resolve(ref.args?.value ?? ''))
      const pat = String(ref.args?.pattern ?? '')
      try { return new RegExp(pat).test(val) } catch { return false }
    }
    return ''
  }

  // Evaluate checks array — returns first failing message or null
  const firstCheckError = (checks?: any[]): string | null => {
    if (!checks?.length) return null
    for (const c of checks) {
      if (!resolve(c.condition)) return c.message
    }
    return null
  }

  // Resolve action context, substituting path refs
  const resolveContext = (ctx: Record<string, any> = {}): Record<string, any> => {
    const out: Record<string, any> = {}
    for (const [k, v] of Object.entries(ctx)) out[k] = resolve(v)
    return out
  }

  // Map variant to element tag + class
  const variantClass = (v?: string) => {
    switch (v) {
      case 'h3': return 'a2ui-h3'
      case 'h4': return 'a2ui-h4'
      case 'h5': return 'a2ui-h5'
      case 'caption': return 'a2ui-caption'
      case 'label': return 'a2ui-label'
      default: return 'a2ui-body'
    }
  }

  const render = (id: string): React.ReactNode => {
    const comp = compMap.get(id)
    if (!comp) return null
    const inlineStyle: React.CSSProperties = {
      ...(comp.style as React.CSSProperties | undefined),
      ...(comp.weight !== undefined ? { flex: comp.weight } : {}),
    }
    const gap = comp.spacing ? { gap: `${comp.spacing}px` } : {}

    switch (comp.component) {
      case 'Column': {
        const alignItems = comp.align === 'center' ? 'center' : comp.align === 'end' ? 'flex-end' : 'flex-start'
        const justifyContent =
          comp.justify === 'spaceBetween' ? 'space-between'
          : comp.justify === 'center' ? 'center'
          : 'flex-start'
        return (
          <div key={id} className="a2ui-column" style={{ alignItems, justifyContent, ...gap, ...inlineStyle }}>
            {(comp.children ?? []).map(cid => render(cid))}
          </div>
        )
      }
      case 'Row': {
        const alignItems = comp.align === 'start' ? 'flex-start' : comp.align === 'end' ? 'flex-end' : 'center'
        const justifyContent =
          comp.justify === 'spaceBetween' ? 'space-between'
          : comp.justify === 'start' ? 'flex-start'
          : comp.justify === 'end' ? 'flex-end'
          : 'center'
        return (
          <div key={id} className="a2ui-row" style={{ alignItems, justifyContent, ...gap, ...inlineStyle }}>
            {(comp.children ?? []).map(cid => render(cid))}
          </div>
        )
      }
      case 'Card':
        return (
          <div key={id} className="a2ui-card" style={inlineStyle}>
            {comp.child ? render(comp.child) : null}
          </div>
        )
      case 'Text': {
        const text = String(resolve(comp.text ?? ''))
        return (
          <span key={id} className={`a2ui-text ${variantClass(comp.variant)}`} style={inlineStyle}>
            {text}
          </span>
        )
      }
      case 'Divider':
        return <hr key={id} className="a2ui-divider" style={inlineStyle} />

      case 'Link': {
        const text = String(resolve(comp.text ?? ''))
        const url = String(resolve(comp.url ?? ''))
        return (
          <a
            key={id}
            className="a2ui-link"
            style={inlineStyle}
            href={url}
            target="_blank"
            rel="noreferrer"
          >
            {text}
          </a>
        )
      }

      case 'Icon': {
        const iconMap: Record<string, IconName> = {
          person: 'user', check: 'check', star: 'star', doc: 'doc', lock: 'lock', warning: 'warning',
        }
        return (
          <span key={id} className="a2ui-icon" style={inlineStyle}>
            <Icon name={iconMap[comp.name ?? ''] ?? 'dot'} size={18} />
          </span>
        )
      }

      case 'TextField': {
        const fieldKey = comp.value?.path ? String(comp.value.path).replace(/^\//, '') : id
        const fieldValue = String(formData[fieldKey] ?? '')
        const checkErr = firstCheckError(comp.checks)
        return (
          <div key={id} className="a2ui-textfield-wrap" style={inlineStyle}>
            {comp.label && <label className="a2ui-textfield-label">{comp.label}</label>}
            <input
              className={`a2ui-textfield${checkErr && fieldValue ? ' a2ui-textfield-error' : ''}`}
              type={comp.variant === 'password' ? 'password' : 'text'}
              inputMode={comp.keyboardType === 'number-pad' ? 'numeric' : undefined}
              value={fieldValue}
              disabled={disabled || loading}
              onChange={e => setField(fieldKey, e.target.value)}
              placeholder={comp.label}
            />
            {checkErr && fieldValue && <span className="a2ui-field-error">{checkErr}</span>}
          </div>
        )
      }

      case 'Button': {
        const checkErr = firstCheckError(comp.checks)
        const isDisabled = disabled || loading || !!checkErr
        const variant = comp.variant ?? 'primary'
        const handleClick = () => {
          if (isDisabled) return
          const eventName = comp.action?.event?.name ?? ''
          const rawContext = comp.action?.event?.context ?? {}
          const ctx = resolveContext(rawContext)
          onEvent?.(eventName, ctx)
        }
        return (
          <button
            key={id}
            className={`a2ui-btn a2ui-btn-${variant}`}
            style={inlineStyle}
            disabled={isDisabled}
            title={checkErr ?? undefined}
            onClick={handleClick}
          >
            {comp.child ? render(comp.child) : null}
          </button>
        )
      }

      default:
        return null
    }
  }

  return <div className="a2ui-surface">{render('root')}</div>
}
