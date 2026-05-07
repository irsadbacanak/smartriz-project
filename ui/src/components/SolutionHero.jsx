import ParameterChip from './ParameterChip'

function formatDate(d) {
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

export default function SolutionHero({ contradiction, problem, meta }) {
  const improving = contradiction?.improving_parameter || 'Improving parameter'
  const worsening = contradiction?.worsening_parameter || 'Worsening parameter'
  const model = meta?.model || 'local model'
  const duration =
    typeof meta?.duration_seconds === 'number' ? `${meta.duration_seconds.toFixed(1)}s` : '—'
  const generated = formatDate(new Date())

  return (
    <div className="solution-hero">
      <div className="hero-left">
        <p className="hero-label">Identified contradiction</p>
        <div className="hero-chips">
          <ParameterChip label={`↑ ${improving}`} trend="up" />
          <span className="chip-conflict">conflicts with</span>
          <ParameterChip label={`↓ ${worsening}`} trend="down" />
        </div>
        {problem ? <p className="hero-problem-summary">{problem}</p> : null}
      </div>
      <div className="hero-right">
        <div className="meta-strip">
          <span>
            Model: <span className="meta-mono">{model}</span>
          </span>
          <span>
            Duration: <span className="meta-mono">{duration}</span>
          </span>
          <span>
            Generated: <span className="meta-mono">{generated}</span>
          </span>
        </div>
      </div>
    </div>
  )
}
