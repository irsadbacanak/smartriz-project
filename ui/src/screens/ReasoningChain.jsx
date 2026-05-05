import { useMemo, useState } from 'react'

function enrichLine(line) {
  return line
    .replace(/\b(Weight|Strength|Reliability|Temperature|Productivity)\b/g, '<span class="hl-parameter">$1</span>')
    .replace(/\bP(\d{1,2})\b/g, '<span class="hl-principle">[P$1]</span>')
    .replace(/\b(as in[^.]+)\b/gi, '<em class="hl-analogy">$1</em>')
}

export default function ReasoningChain({ text }) {
  const [open, setOpen] = useState(false)
  const rendered = useMemo(() => text.split('\n').map((line) => enrichLine(line)).join('<br/>'), [text])

  return (
    <section className="reasoning-screen">
      <button className="text-button reasoning-toggle" onClick={() => setOpen((v) => !v)} type="button">
        See full reasoning chain {open ? '↑' : '↓'}
      </button>
      {open ? <div className="reasoning-content" dangerouslySetInnerHTML={{ __html: rendered }} /> : null}
    </section>
  )
}
