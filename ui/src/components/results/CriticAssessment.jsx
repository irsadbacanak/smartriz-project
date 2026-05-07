export function CriticAssessment({ feedback }) {
  if (!feedback) return null
  return (
    <section className="critic-section">
      <h4>AI Critic Assessment</h4>
      <blockquote className="critic-quote">{feedback}</blockquote>
    </section>
  )
}
