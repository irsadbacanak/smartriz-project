const AGENT_DEFS = [
  { id: 'analyst', label: 'Problem Analyst' },
  { id: 'detector', label: 'Contradiction Detector' },
  { id: 'solver', label: 'ReAct Solver' },
  { id: 'critic', label: 'Reflexion Critic' },
]

function statusIcon(status) {
  if (status === 'done') return '✓'
  if (status === 'active') return '⟳'
  return '·'
}

export default function AgentPipeline({ agentStates, problem }) {
  const completedCount = AGENT_DEFS.filter(a => agentStates[a.id]?.status === 'done').length
  const pct = completedCount * 25

  return (
    <div className="analysis-progress">
      {problem && (
        <p className="analysis-problem">
          {problem.length > 120 ? problem.slice(0, 120) + '…' : problem}
        </p>
      )}
      {AGENT_DEFS.map(({ id, label }) => {
        const st = agentStates[id] ?? { status: 'waiting', logLine: '' }
        return (
          <div key={id} className={`agent-row agent-${st.status}`}>
            <span className="agent-status-icon">{statusIcon(st.status)}</span>
            <div>
              <span className="agent-name">{label}</span>
              {st.logLine && <p className="agent-log">{st.logLine}</p>}
            </div>
          </div>
        )
      })}
      <div className="progress-bar-wrapper">
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${pct}%` }} />
        </div>
        <span className="progress-pct">{pct}%</span>
      </div>
    </div>
  )
}
