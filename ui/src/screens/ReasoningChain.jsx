import { useMemo, useState } from 'react'

function buildMarkdown(state) {
  if (!state) return ''
  const sections = []

  if (state.analysis) {
    sections.push(`## 1. Problem Analysis\n\n${state.analysis}`)
  }

  const contradictions = state.contradictions || []
  if (contradictions.length > 0) {
    const items = contradictions.map((c) => `- ${c}`).join('\n')
    sections.push(`## 2. Identified Contradictions\n\n${items}`)
  }

  const principles = state.selected_principles || []
  if (principles.length > 0) {
    const items = principles.map((p) => `- ${p}`).join('\n')
    sections.push(`## 3. Selected TRIZ Principles\n\n${items}`)
  }

  if (state.final_solution) {
    sections.push(`## 4. Proposed Solution\n\n${state.final_solution}`)
  }

  if (state.critic_feedback) {
    sections.push(`## 5. Critic Feedback\n\n${state.critic_feedback}`)
  }

  return sections.join('\n\n')
}

function renderMarkdown(markdown) {
  return markdown
    .split('\n')
    .map((line) => {
      if (line.startsWith('## ')) return `<h3>${line.slice(3)}</h3>`
      if (line.startsWith('- ')) return `<li>${line.slice(2)}</li>`
      if (line === '') return '<br/>'
      return `<p>${line}</p>`
    })
    .join('')
}

export default function ReasoningChain({ state }) {
  const [open, setOpen] = useState(false)
  const rendered = useMemo(() => renderMarkdown(buildMarkdown(state)), [state])

  return (
    <section className="reasoning-screen">
      <button className="text-button reasoning-toggle" onClick={() => setOpen((v) => !v)} type="button">
        See full reasoning chain {open ? '↑' : '↓'}
      </button>
      {open ? <div className="reasoning-content" dangerouslySetInnerHTML={{ __html: rendered }} /> : null}
    </section>
  )
}
