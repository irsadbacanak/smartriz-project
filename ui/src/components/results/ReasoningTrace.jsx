export function ReasoningTrace({ state }) {
  if (!state) return null
  return (
    <details className="reasoning-trace">
      <summary>View AI reasoning chain</summary>
      <div className="reasoning-sections">
        {state.analysis && (
          <section>
            <h4>1. Problem Analysis</h4>
            <p>{state.analysis}</p>
          </section>
        )}
        {state.contradictions?.length > 0 && (
          <section>
            <h4>2. Identified Contradictions</h4>
            <ul>
              {state.contradictions.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </section>
        )}
        {state.selected_principles?.length > 0 && (
          <section>
            <h4>3. Selected TRIZ Principles</h4>
            <ul>
              {state.selected_principles.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          </section>
        )}
        {state.final_solution && (
          <section>
            <h4>4. Proposed Solution</h4>
            <p>{state.final_solution}</p>
          </section>
        )}
        {state.critic_feedback && (
          <section>
            <h4>5. Critic Feedback</h4>
            <p>{state.critic_feedback}</p>
          </section>
        )}
      </div>
    </details>
  )
}
