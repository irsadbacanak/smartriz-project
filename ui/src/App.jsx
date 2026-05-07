import { useMemo, useState } from 'react'
import Breadcrumb from './components/Breadcrumb'
import { ActionsFooter } from './components/results/ActionsFooter'
import { ContradictionCard } from './components/results/ContradictionCard'
import { CriticAssessment } from './components/results/CriticAssessment'
import { PrinciplesGrid } from './components/results/PrinciplesGrid'
import { ReasoningTrace } from './components/results/ReasoningTrace'
import { ReferenceMatrix } from './components/results/ReferenceMatrix'
import { ResultHeader } from './components/results/ResultHeader'
import { ProblemSummary } from './components/results/ProblemSummary'
import { SolutionText } from './components/results/SolutionText'
import { casesMock } from './data/casesMock'
import { matrixMock } from './data/matrixMock'
import { parameters } from './data/parameters'
import { principles } from './data/principles'
import { useTrizStream } from './hooks/useTrizStream'
import AgentPipeline from './screens/AgentPipeline'
import PrincipleDetailPanel from './screens/PrincipleDetailPanel'
import ProblemInput from './screens/ProblemInput'
import './App.css'

function resolvePair(result) {
  const detail = result?.contradiction_details?.[0]
  if (detail) {
    const imp = detail.improving_id
    const wors = detail.worsening_id
    if (
      Number.isInteger(imp) &&
      Number.isInteger(wors) &&
      imp >= 1 &&
      imp <= 39 &&
      wors >= 1 &&
      wors <= 39
    ) {
      return { improvingId: imp, worseningId: wors }
    }
  }
  return { improvingId: 27, worseningId: 14 }
}

function parsePrincipleEntry(entry) {
  const match = entry.match(/^(\d+):\s*(.+)$/)
  if (match) {
    return { id: parseInt(match[1], 10), name: match[2].trim() }
  }
  return null
}

export default function App() {
  const [problem, setProblem] = useState('')
  const [domain, setDomain] = useState('')
  const [expandedPrinciple, setExpandedPrinciple] = useState(null)
  const { status, result, error, agentStates, currentStep, start, reset } = useTrizStream()

  const pair = useMemo(() => resolvePair(result), [result])

  const recommendedPrinciples = useMemo(() => {
    const modelPrinciples = result?.selected_principles
    if (modelPrinciples && modelPrinciples.length > 0) {
      const cards = modelPrinciples
        .slice(0, 4)
        .map((entry) => {
          const parsed = parsePrincipleEntry(entry)
          if (!parsed) return null
          const found = principles.find((p) => p.id === parsed.id)
          return found || { id: parsed.id, name: parsed.name, description: parsed.name }
        })
        .filter(Boolean)
      if (cards.length > 0) return cards
    }
    const matrixKey = `${pair.improvingId}-${pair.worseningId}`
    const ids = matrixMock[matrixKey] || [15, 35, 1]
    return principles.filter((item) => ids.includes(item.id))
  }, [result, pair])

  const domainCases = useMemo(() => {
    if (!domain) return []
    const selected = casesMock.filter((item) => item.domain === domain)
    return selected.length ? selected : casesMock
  }, [domain])

  const handleAnalyze = () => {
    if (!problem.trim()) return
    start(problem)
  }

  const handleRefine = () => {
    reset()
    setExpandedPrinciple(null)
  }

  return (
    <div className="app-shell">
      {status !== 'idle' ? <Breadcrumb currentStep={currentStep} /> : null}

      {status === 'idle' || status === 'error' ? (
        <>
          <ProblemInput
            problem={problem}
            domain={domain}
            improvementParameter=""
            onProblemChange={setProblem}
            onDomainChange={setDomain}
            onImprovementParameterChange={() => {}}
            onAnalyze={handleAnalyze}
          />
          {error ? <p className="inline-error">{error}</p> : null}
        </>
      ) : null}

      {status === 'running' ? <AgentPipeline agentStates={agentStates} problem={problem} /> : null}

      {status === 'complete' ? (
        <main className="results-page">
          <ResultHeader meta={result?.meta} onBack={handleRefine} />
          <ProblemSummary problem={problem} domain={domain} />
          <ContradictionCard
            details={result?.contradiction_details?.[0]}
            contradictions={result?.contradictions}
          />
          <PrinciplesGrid
            principles={recommendedPrinciples}
            applications={result?.principle_applications}
            onExpand={setExpandedPrinciple}
          />
          <SolutionText text={result?.final_solution} />
          <CriticAssessment feedback={result?.critic_feedback} />
          <ReferenceMatrix
            parameters={parameters}
            improvingId={pair.improvingId}
            worseningId={pair.worseningId}
            matrixMap={matrixMock}
            principleIds={recommendedPrinciples.map(p => p.id)}
          />
          <ReasoningTrace state={result} />
          <ActionsFooter onRefine={handleRefine} />
          <PrincipleDetailPanel
            principle={expandedPrinciple}
            cases={domainCases}
            onApply={() => setExpandedPrinciple(null)}
            onClose={() => setExpandedPrinciple(null)}
          />
        </main>
      ) : null}
    </div>
  )
}
