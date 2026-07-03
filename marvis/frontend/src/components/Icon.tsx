// Shared line-icon set — one consistent vocabulary (24×24, 1.8 stroke, round
// caps/joins) matching the Sidebar icons. Replaces the emoji used across the
// landing page, chat activity feed, and A2UI payment cards, which rendered
// inconsistently per-OS and read as generic.

export type IconName =
  | 'chat' | 'sparkle' | 'bolt' | 'check' | 'checkCircle'
  | 'shieldCheck' | 'shield' | 'lock' | 'key' | 'receipt'
  | 'cart' | 'wallet' | 'gear' | 'swap' | 'search'
  | 'user' | 'star' | 'doc' | 'warning' | 'cash' | 'dot'

interface Props {
  name: IconName
  size?: number
  className?: string
}

// Each entry returns the inner geometry; the wrapper supplies the shared
// stroke/fill defaults so every glyph stays visually consistent.
const PATHS: Record<IconName, React.ReactNode> = {
  chat: <path d="M4 5h16v11H8l-4 4V5z" strokeLinejoin="round" />,
  sparkle: <path d="M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7z" strokeLinejoin="round" />,
  bolt: <path d="M13 3L5 13.5h6L10 21l8-10.5h-6L13 3z" strokeLinejoin="round" />,
  check: <path d="M4 12.5l5 5L20 6.5" strokeLinecap="round" strokeLinejoin="round" />,
  checkCircle: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M8 12l2.6 2.6L16 9" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  shieldCheck: (
    <>
      <path d="M12 3l7 3v6c0 4-3 6.6-7 8-4-1.4-7-4-7-8V6l7-3z" strokeLinejoin="round" />
      <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  shield: <path d="M12 3l7 3v6c0 4-3 6.6-7 8-4-1.4-7-4-7-8V6l7-3z" strokeLinejoin="round" />,
  lock: (
    <>
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </>
  ),
  key: (
    <>
      <circle cx="7.5" cy="15.5" r="3.5" />
      <path d="M10 13l8-8M16 7l2.4 2.4M14 9l2 2" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  receipt: (
    <>
      <path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3z" strokeLinejoin="round" />
      <path d="M9 8h6M9 12h6" strokeLinecap="round" />
    </>
  ),
  cart: (
    <>
      <path d="M4 9h16l-1.2 8H5.2L4 9z" strokeLinejoin="round" />
      <path d="M4 9l1.5-4h13L20 9" strokeLinejoin="round" />
      <path d="M9 13c0 1.7 1.3 3 3 3s3-1.3 3-3" strokeLinecap="round" />
    </>
  ),
  wallet: (
    <>
      <rect x="3" y="6" width="18" height="13" rx="2.5" />
      <path d="M3 10.5h18" />
      <circle cx="16.5" cy="14.8" r="1.3" fill="currentColor" stroke="none" />
    </>
  ),
  gear: (
    <>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.2 5.2l2.1 2.1M16.7 16.7l2.1 2.1M18.8 5.2l-2.1 2.1M7.3 16.7l-2.1 2.1" strokeLinecap="round" />
    </>
  ),
  swap: (
    <>
      <path d="M7 8h11l-3-3M17 16H6l3 3" strokeLinecap="round" strokeLinejoin="round" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3.6-3.6" strokeLinecap="round" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c0-4 3.6-6 8-6s8 2 8 6" strokeLinecap="round" />
    </>
  ),
  star: <path d="M12 3.5l2.5 5.3 5.5.8-4 4 .9 5.6L12 16.6 7.1 19.2l.9-5.6-4-4 5.5-.8z" strokeLinejoin="round" />,
  doc: (
    <>
      <path d="M7 3h7l4 4v14H7z" strokeLinejoin="round" />
      <path d="M14 3v4h4M9.5 12h5M9.5 15.5h5" strokeLinecap="round" />
    </>
  ),
  warning: (
    <>
      <path d="M12 3.5l9 16H3l9-16z" strokeLinejoin="round" />
      <path d="M12 9.5v4.5M12 17.5h.01" strokeLinecap="round" />
    </>
  ),
  cash: (
    <>
      <rect x="2.5" y="6" width="19" height="12" rx="2" />
      <circle cx="12" cy="12" r="2.6" />
      <path d="M6 10v4M18 10v4" strokeLinecap="round" />
    </>
  ),
  dot: <circle cx="12" cy="12" r="3" fill="currentColor" stroke="none" />,
}

export default function Icon({ name, size = 20, className }: Props) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      aria-hidden
    >
      {PATHS[name]}
    </svg>
  )
}
