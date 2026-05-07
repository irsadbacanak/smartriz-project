import PrincipleCard from './PrincipleCard'

function parseSolution(text) {
  if (!text) return []
  const lines = text.split('\n')
  const result = []
  let paragraphLines = []

  const flush = () => {
    const content = paragraphLines.join(' ').trim()
    if (content) result.push({ type: 'p', content })
    paragraphLines = []
  }

  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed === '') {
      flush()
    } else if (/^[-*]\s/.test(trimmed)) {
      flush()
      result.push({ type: 'li', content: trimmed.replace(/^[-*]\s/, '') })
    } else if (/^\d+\.\s/.test(trimmed)) {
      flush()
      result.push({ type: 'li', content: trimmed.replace(/^\d+\.\s/, '') })
    } else {
      paragraphLines.push(trimmed)
    }
  }
  flush()
  return result
}

export default function SolutionBody({
  finalSolution,
  principles,
  principleApplications,
  criticFeedback,
  onExpandPrinciple,
}) {
  const blocks = parseSolution(finalSolution)
  const listItems = blocks.filter((b) => b.type === 'li')
  const paragraphs = blocks.filter((b) => b.type === 'p')

  return (
    <div className="solution-body">
      <section className="solution-section-block">
        <h3 className="solution-section-title">Proposed solution</h3>
        <div className="solution-text">
          {paragraphs.map((b, i) => (
            <p key={i}>{b.content}</p>
          ))}
          {listItems.length > 0 ? (
            <ul className="solution-list">
              {listItems.map((b, i) => (
                <li key={i}>{b.content}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </section>

      {principles && principles.length > 0 ? (
        <section className="solution-section-block">
          <h3 className="solution-section-title">Principles applied</h3>
          <div className="principles-grid">
            {principles.map((p) => (
              <PrincipleCard
                key={p.id}
                principle={p}
                onExpand={onExpandPrinciple}
                application={principleApplications?.[String(p.id)] ?? null}
              />
            ))}
          </div>
        </section>
      ) : null}

      {criticFeedback ? (
        <section className="solution-section-block">
          <h3 className="solution-section-title">Critic insight</h3>
          <blockquote className="critic-blockquote">{criticFeedback}</blockquote>
        </section>
      ) : null}
    </div>
  )
}
