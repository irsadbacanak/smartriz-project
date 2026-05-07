export default function ParameterChip({ label, trend = 'up' }) {
  return (
    <div className="parameter-chip">
      <span className="chip-label">{label.toUpperCase()}</span>
      <svg viewBox="0 0 12 12" className="chip-arrow" aria-hidden="true">
        {trend === 'up' ? <path d="M6 1 11 7H7v4H5V7H1z" /> : <path d="M6 11 1 5h4V1h2v4h4z" />}
      </svg>
    </div>
  )
}
