// Tiny pub/sub so any action that moves money (top-up, a PIN-confirmed
// payment) can tell the Sidebar's live balance to refetch immediately,
// instead of waiting for its next poll tick.
const EVENT = 'marvis:balance-changed'

export function notifyBalanceChanged() {
  window.dispatchEvent(new Event(EVENT))
}

export function onBalanceChanged(handler: () => void): () => void {
  window.addEventListener(EVENT, handler)
  return () => window.removeEventListener(EVENT, handler)
}
