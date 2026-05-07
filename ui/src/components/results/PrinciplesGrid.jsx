import PrincipleCard from '../PrincipleCard'

export function PrinciplesGrid({ principles, applications, onExpand }) {
  if (!principles?.length) return null
  return (
    <section className="principles-section">
      <h3>Applied Principles</h3>
      <div className="principles-grid">
        {principles.map(p => (
          <PrincipleCard
            key={p.id}
            principle={p}
            application={applications?.[String(p.id)]}
            onExpand={onExpand}
          />
        ))}
      </div>
    </section>
  )
}
