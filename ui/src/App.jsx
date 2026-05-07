import { useMemo, useState } from 'react'
import Breadcrumb from './components/Breadcrumb'
import { casesMock } from './data/casesMock'
import { matrixMock } from './data/matrixMock'
import { parameters } from './data/parameters'
import { principles } from './data/principles'
import { useTrizStream } from './hooks/useTrizStream'
import AgentPipeline from './screens/AgentPipeline'
import ContradictionMatrix from './screens/ContradictionMatrix'
import PrincipleDetailPanel from './screens/PrincipleDetailPanel'
import ProblemInput from './screens/ProblemInput'
import ReasoningChain from './screens/ReasoningChain'
import SolutionOutput from './screens/SolutionOutput'
import './App.css'

function resolvePair(result, contradictionText) {
  const detail = result?.contradiction_details?.[0]
  if (detail) {
    const imp = detail.improving_id
    const wors = detail.worsening_id
    if (Number.isInteger(imp) && Number.isInteger(wors) && imp >= 1 && imp <= 39 && wors >= 1 && wors <= 39) {
      return { improvingId: imp, worseningId: wors }
    }
  }
  console.warn('[SmarTRIZ] Using heuristic pair resolution — contradiction_details not available')
  const source = (contradictionText || '').toLowerCase()
  if (source.includes('weight') && source.includes('strength')) {
    return { improvingId: 1, worseningId: 14 }
  }
  if (source.includes('reliability') && source.includes('strength')) {
    return { improvingId: 27, worseningId: 14 }
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
  const [improvementParameter, setImprovementParameter] = useState('')
  const [expandedPrinciple, setExpandedPrinciple] = useState(null)
  const { status, result, error, agentStates, currentStep, start, reset } = useTrizStream()

  const pair = useMemo(
    () => resolvePair(result, result?.contradictions?.[0] || improvementParameter),
    [result, improvementParameter],
  )
  const matrixKey = `${pair.improvingId}-${pair.worseningId}`

  const recommendedPrinciples = useMemo(() => {
    const modelPrinciples = result?.selected_principles
    if (modelPrinciples && modelPrinciples.length > 0) {
      const cards = modelPrinciples.slice(0, 4).map((entry) => {
        const parsed = parsePrincipleEntry(entry)
        if (!parsed) return null
        const found = principles.find((p) => p.id === parsed.id)
        return found || { id: parsed.id, name: parsed.name, description: parsed.name }
      }).filter(Boolean)
      if (cards.length > 0) return cards
    }
    console.warn('[SmarTRIZ] Using matrixMock fallback for principles — selected_principles not available')
    const ids = matrixMock[matrixKey] || [15, 35, 1]
    return principles.filter((item) => ids.includes(item.id))
  }, [result, matrixKey])

  const domainCases = useMemo(() => {
    if (!domain) return []
    const selected = casesMock.filter((item) => item.domain === domain)
    return selected.length ? selected : casesMock
  }, [domain])

  const confidence = useMemo(() => {
    if (!result) return null
    const contradictions = result.contradictions || []
    const selectedPrinciples = result.selected_principles || []
    return {
      contradictionClarity: contradictions.length === 0 ? 0 : Math.min(1, contradictions.length / 2),
      principleRelevance: selectedPrinciples.length >= 2 ? 0.85 : selectedPrinciples.length === 1 ? 0.6 : 0.3,
      caseSimilarity: domain ? 0.7 : null,
    }
  }, [result, domain])

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
            improvementParameter={improvementParameter}
            onProblemChange={setProblem}
            onDomainChange={setDomain}
            onImprovementParameterChange={setImprovementParameter}
            onAnalyze={handleAnalyze}
          />
          {error ? <p className="inline-error">{error}</p> : null}
        </>
      ) : null}

      {status === 'running' ? <AgentPipeline agentStates={agentStates} /> : null}

      {status === 'complete' ? (
        <main className="results-layout">
          <ContradictionMatrix
            parameters={parameters}
            improvingId={pair.improvingId}
            worseningId={pair.worseningId}
            matrixMap={matrixMock}
            recommendedPrinciples={recommendedPrinciples}
            onExpandPrinciple={setExpandedPrinciple}
          />

          <ReasoningChain state={result} />

          <SolutionOutput
            improvingLabel={parameters[pair.improvingId - 1].name}
            worseningLabel={parameters[pair.worseningId - 1].name}
            principles={recommendedPrinciples}
            cases={domainCases}
            finalSolution={result?.final_solution}
            confidence={confidence}
            onRefine={handleRefine}
          />

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
