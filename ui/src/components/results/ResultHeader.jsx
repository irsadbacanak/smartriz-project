export function ResultHeader({ meta, onBack }) {
  const model = meta?.model ?? 'local model'
  const duration = meta?.duration_seconds != null ? `${meta.duration_seconds.toFixed(1)}s` : null
  const date = new Date().toLocaleDateString()
  return (
    <header className="result-header">
      <button type="button" className="text-button" onClick={onBack}>
        ← Back to problem
      </button>
      <span className="result-meta">
        {model}{duration ? ` · ${duration}` : ''} · {date}
      </span>
    </header>
  )
}
