export function ContradictionCard({ details, contradictions }) {
  if (!details) return null
  const { improving_parameter, worsening_parameter, improving_id, worsening_id } = details
  const description = contradictions?.[0] ?? null
  return (
    <section className="contradiction-card">
      <div className="contradiction-pair">
        <div className="contradiction-chip improving">
          <span className="chip-arrow">↑ Improving</span>
          <strong>{improving_parameter}</strong>
          {improving_id && <code>#{improving_id}</code>}
        </div>
        <span className="contradiction-tension">conflicts with</span>
        <div className="contradiction-chip worsening">
          <span className="chip-arrow">↓ Worsening</span>
          <strong>{worsening_parameter}</strong>
          {worsening_id && <code>#{worsening_id}</code>}
        </div>
      </div>
      {description && <p className="contradiction-description">{description}</p>}
    </section>
  )
}
