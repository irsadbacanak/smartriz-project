import LogoMark from '../components/LogoMark'

const DOMAINS = ['Aerospace', 'Mechanical', 'Thermal', 'Electrical', 'Other']

export default function ProblemInput({
  problem,
  domain,
  improvementParameter,
  onProblemChange,
  onDomainChange,
  onImprovementParameterChange,
  onAnalyze,
}) {
  const hasInput = problem.trim().length > 0

  return (
    <section className="input-screen">
      <div className="brand-row">
        <LogoMark />
        <div>
          <h1 className="brand-title">SmarTRIZ</h1>
          <p className="brand-tagline">State the engineering problem to analyze.</p>
        </div>
      </div>

      <textarea
        className="problem-textarea"
        value={problem}
        onChange={(event) => onProblemChange(event.target.value)}
        placeholder="Describe the technical system and what isn't working as expected."
        rows={6}
      />

      {hasInput ? (
        <div className="secondary-fields">
          <label className="secondary-field">
            <span>Domain</span>
            <select value={domain} onChange={(event) => onDomainChange(event.target.value)}>
              <option value="">Optional</option>
              {DOMAINS.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="secondary-field">
            <span>Improvement parameter</span>
            <input
              value={improvementParameter}
              onChange={(event) => onImprovementParameterChange(event.target.value)}
              placeholder="Optional"
            />
          </label>
        </div>
      ) : null}

      <button className="primary-button large-button" type="button" onClick={onAnalyze}>
        Analyze contradiction →
      </button>
    </section>
  )
}
