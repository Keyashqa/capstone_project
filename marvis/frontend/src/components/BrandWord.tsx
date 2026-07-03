// Highlights the leading "M" of a brand-relevant word (Marvis, MPay, Marketplace…)
// in the brand accent color, tying it visually back to Marvis the platform.
export default function BrandWord({ text }: { text: string }) {
  return (
    <span className="brand-word">
      <span className="brand-word-m">{text.charAt(0)}</span>{text.slice(1)}
    </span>
  )
}
