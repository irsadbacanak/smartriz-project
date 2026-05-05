export default function SimilarityBar({ value = 0.5 }) {
  const width = Math.max(0, Math.min(100, Math.round(value * 100)))
  return (
    <div className="bar-track" aria-label="similarity">
      <div className="bar-fill" style={{ width: `${width}%` }} />
    </div>
  )
}
