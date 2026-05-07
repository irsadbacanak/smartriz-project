export function ProblemSummary({ problem, domain }) {
  return (
    <section className="problem-summary">
      {domain && <span className="domain-badge">{domain}</span>}
      <p>{problem}</p>
    </section>
  )
}
