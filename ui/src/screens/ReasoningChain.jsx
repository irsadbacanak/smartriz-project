function ReasoningSections({ state }) {
  const sections = []

  if (state.analysis) {
    sections.push({
      title: '1. Problem Analysis',
      content: <p>{state.analysis}</p>,
    })
  }

  const contradictions = state.contradictions || []
  if (contradictions.length > 0) {
    sections.push({
      title: '2. Identified Contradictions',
      content: (
        <ul>
          {contradictions.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      ),
    })
  }

  const principles = state.selected_principles || []
  if (principles.length > 0) {
    sections.push({
      title: '3. Selected TRIZ Principles',
      content: (
        <ul>
          {principles.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      ),
    })
  }

  if (state.final_solution) {
    sections.push({
      title: '4. Proposed Solution',
      content: <p>{state.final_solution}</p>,
    })
  }

  if (state.critic_feedback) {
    sections.push({
      title: '5. Critic Feedback',
      content: <p>{state.critic_feedback}</p>,
    })
  }

  return (
    <>
      {sections.map((s) => (
        <section className="reasoning-section" key={s.title}>
          <h3>{s.title}</h3>
          {s.content}
        </section>
      ))}
    </>
  )
}

export default function ReasoningChain({ state }) {
  return (
    <details className="reasoning-screen">
      <summary className="text-button reasoning-toggle">See full reasoning chain</summary>
      <div className="reasoning-content">
        <ReasoningSections state={state} />
      </div>
    </details>
  )
}
