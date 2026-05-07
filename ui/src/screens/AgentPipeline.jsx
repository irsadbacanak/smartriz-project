import AgentNode from '../components/AgentNode'

const AGENTS = [
  { id: 'analyst', name: 'Problem Analyst' },
  { id: 'detector', name: 'Contradiction Detector' },
  { id: 'solver', name: 'ReAct Solver' },
  { id: 'critic', name: 'Reflexion Critic' },
]

export default function AgentPipeline({ agentStates }) {
  return (
    <section className="pipeline-screen">
      <div className="timeline-column" aria-hidden="true" />
      <div className="pipeline-content">
        {AGENTS.map((agent) => (
          <AgentNode
            key={agent.id}
            name={agent.name}
            status={agentStates[agent.id].status}
            logLine={agentStates[agent.id].logLine}
          />
        ))}
      </div>
    </section>
  )
}
