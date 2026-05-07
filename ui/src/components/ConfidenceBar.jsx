export default function ConfidenceBar({ label, value }) {
  return (
    <div className="confidence-row">
      <span className="confidence-label">{label}</span>
      <div className="bar-track">
        <div className="bar-fill confidence-fill" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
    </div>
  )
}
