import CaseCard from '../components/CaseCard'
import ConfidenceBar from '../components/ConfidenceBar'
import ParameterChip from '../components/ParameterChip'

export default function SolutionOutput({
  improvingLabel,
  worseningLabel,
  principles,
  cases,
  finalSolution,
  confidence,
  onRefine,
}) {
  const bullets = finalSolution
    ? finalSolution.split('.').map((item) => item.trim()).filter(Boolean).slice(0, 4)
    : []

  const showCases = cases && cases.length > 0

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

      {showCases ? (
        <div className="solution-section">
          <h3>Reference cases (offline knowledge base)</h3>
          <div className="cases-grid">
            {cases.slice(0, 2).map((item) => (
              <CaseCard key={item.id} item={item} />
            ))}
          </div>
        </div>
      ) : null}

      {confidence ? (
        <div className="solution-section">
          <h3>Confidence indicators</h3>
          <ConfidenceBar label="Contradiction clarity" value={confidence.contradictionClarity} />
          <ConfidenceBar label="Principle relevance" value={confidence.principleRelevance} />
          {confidence.caseSimilarity !== null ? (
            <ConfidenceBar label="Case similarity" value={confidence.caseSimilarity} />
          ) : null}
        </div>
      ) : null}

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
