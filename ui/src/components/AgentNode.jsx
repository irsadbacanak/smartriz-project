export default function AgentNode({ name, status, logLine }) {
  return (
    <div className="agent-row">
      <span className={`timeline-node ${status}`}>{status === 'done' ? '✓' : ''}</span>
      <div className="agent-meta">
        <div className="agent-name">{name}</div>
        <div className="agent-log">{logLine}</div>
      </div>
    </div>
  )
}
