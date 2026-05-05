import CaseCard from '../components/CaseCard'
import ConfidenceBar from '../components/ConfidenceBar'
import ParameterChip from '../components/ParameterChip'

export default function SolutionOutput({
  improvingLabel,
  worseningLabel,
  principles,
  cases,
  finalSolution,
  onRefine,
}) {
  const bullets = finalSolution
    ? finalSolution.split('.').map((item) => item.trim()).filter(Boolean).slice(0, 4)
    : []

  return (
    <section className="solution-card">
      <div className="solution-section">
        <h3>Identified contradiction</h3>
        <div className="chip-row">
          <ParameterChip label={improvingLabel} trend="up" />
          <ParameterChip label={worseningLabel} trend="down" />
        </div>
      </div>

      <div className="solution-section">
        <h3>Recommended principles</h3>
        <div className="recommended-row">
          {principles.slice(0, 4).map((item) => (
            <span className="recommend-pill" key={item.id}>
              <span className="numeric">P{item.id}</span> {item.name}
            </span>
          ))}
        </div>
      </div>

      <div className="solution-section">
        <h3>Proposed solution</h3>
        <ul className="solution-list">
          {bullets.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>

      <div className="solution-section">
        <h3>Similar resolved cases</h3>
        <div className="cases-grid">
          {cases.slice(0, 2).map((item) => (
            <CaseCard key={item.id} item={item} />
          ))}
        </div>
      </div>

      <div className="solution-section">
        <h3>Confidence indicators</h3>
        <ConfidenceBar label="Contradiction clarity" value={0.78} />
        <ConfidenceBar label="Principle relevance" value={0.72} />
        <ConfidenceBar label="Case similarity" value={0.66} />
      </div>

      <div className="footer-actions">
        <button className="outline-button" type="button">
          Export as PDF
        </button>
        <button className="primary-button" type="button" onClick={onRefine}>
          Refine problem →
        </button>
      </div>
    </section>
  )
}
