function parseSolution(text) {
  if (!text) return []
  return text.split(/\n\n+/).map((block, i) => {
    const lines = block.split('\n').filter(l => l.trim())
    if (lines.length === 0) return null
    if (lines.every(l => /^[-*]\s/.test(l.trim()))) {
      return (
        <ul key={i}>
          {lines.map((l, j) => (
            <li key={j}>{l.trim().replace(/^[-*]\s/, '')}</li>
          ))}
        </ul>
      )
    }
    if (lines.every(l => /^\d+\.\s/.test(l.trim()))) {
      return (
        <ol key={i}>
          {lines.map((l, j) => (
            <li key={j}>{l.trim().replace(/^\d+\.\s+/, '')}</li>
          ))}
        </ol>
      )
    }
    return <p key={i}>{block.trim()}</p>
  }).filter(Boolean)
}

export function SolutionText({ text }) {
  if (!text) return null
  return (
    <section className="solution-text">
      <h3>Proposed Solution</h3>
      <div className="solution-body">{parseSolution(text)}</div>
    </section>
  )
}
