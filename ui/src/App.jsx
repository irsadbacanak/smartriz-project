import { useMemo, useState } from 'react'
import Breadcrumb from './components/Breadcrumb'
import { casesMock } from './data/casesMock'
import { matrixMock } from './data/matrixMock'
import { parameters } from './data/parameters'
import { principles } from './data/principles'
import { reasoningMock } from './data/reasoningMock'
import { useTrizStream } from './hooks/useTrizStream'
import AgentPipeline from './screens/AgentPipeline'
import ContradictionMatrix from './screens/ContradictionMatrix'
import PrincipleDetailPanel from './screens/PrincipleDetailPanel'
import ProblemInput from './screens/ProblemInput'
import ReasoningChain from './screens/ReasoningChain'
import SolutionOutput from './screens/SolutionOutput'
import './App.css'

function resolvePair(contradictionText) {
  const source = (contradictionText || '').toLowerCase()
  if (source.includes('weight') && source.includes('strength')) {
    return { improvingId: 1, worseningId: 14 }
  }
  if (source.includes('reliability') && source.includes('strength')) {
    return { improvingId: 27, worseningId: 14 }
  }
  return { improvingId: 27, worseningId: 14 }
}

export default function App() {
  const [problem, setProblem] = useState('')
  const [domain, setDomain] = useState('')
  const [improvementParameter, setImprovementParameter] = useState('')
  const [expandedPrinciple, setExpandedPrinciple] = useState(null)
  const { status, result, error, agentStates, currentStep, start, reset } = useTrizStream()

  const pair = useMemo(
    () => resolvePair(result?.contradictions?.[0] || improvementParameter),
    [result?.contradictions, improvementParameter],
  )
  const matrixKey = `${pair.improvingId}-${pair.worseningId}`

  const recommendedPrinciples = useMemo(() => {
    const ids = matrixMock[matrixKey] || [15, 35, 1]
    return principles.filter((item) => ids.includes(item.id))
  }, [matrixKey])

  const domainCases = useMemo(() => {
    if (!domain) return casesMock
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

          <ReasoningChain text={reasoningMock} />

          <SolutionOutput
            improvingLabel={parameters[pair.improvingId - 1].name}
            worseningLabel={parameters[pair.worseningId - 1].name}
            principles={recommendedPrinciples}
            cases={domainCases}
            finalSolution={result?.final_solution}
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
