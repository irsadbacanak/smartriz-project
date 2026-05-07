import { useCallback, useMemo, useRef, useState } from 'react'

const STEP_ORDER = ['analyst', 'detector', 'solver', 'critic']

const initialAgentState = {
  analyst: { status: 'waiting', logLine: 'Waiting for input.' },
  detector: { status: 'waiting', logLine: 'Waiting for upstream output.' },
  solver: { status: 'waiting', logLine: 'Waiting for contradiction mapping.' },
  critic: { status: 'waiting', logLine: 'Waiting for candidate solution.' },
}

function deriveLogLine(agent, updates) {
  const truncate = (str, max) => (str && str.length > max ? str.slice(0, max - 1) + '…' : str || '')
  const firstSentence = (str) => {
    if (!str) return ''
    const m = str.match(/[^.!?]+[.!?]/)
    return truncate(m ? m[0].trim() : str.trim(), 110)
  }

  switch (agent) {
    case 'analyst': {
      return firstSentence(updates.analysis) || 'Analysis complete.'
    }
    case 'detector': {
      return updates.contradictions?.[0] || 'No contradiction parsed.'
    }
    case 'solver': {
      const principles = updates.selected_principles ?? []
      const names = principles.slice(0, 2).join(', ')
      return `${principles.length} principle${principles.length !== 1 ? 's' : ''} selected${names ? ': ' + names : ''}`
    }
    case 'critic': {
      return firstSentence(updates.critic_feedback) || 'Evaluation complete.'
    }
    default:
      return 'Step complete.'
  }
}

export function useTrizStream() {
  const [status, setStatus] = useState('idle')
  const [result, setResult] = useState(null)
  const [partialResult, setPartialResult] = useState(null)
  const [error, setError] = useState('')
  const [agentStates, setAgentStates] = useState(initialAgentState)
  const sourceRef = useRef(null)

  const reset = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close()
      sourceRef.current = null
    }
    setStatus('idle')
    setResult(null)
    setPartialResult(null)
    setError('')
    setAgentStates(initialAgentState)
  }, [])

  const start = useCallback((problem) => {
    const trimmed = problem.trim()
    if (!trimmed) return

    if (sourceRef.current) {
      sourceRef.current.close()
    }

    setStatus('running')
    setError('')
    setResult(null)
    setPartialResult(null)
    setAgentStates(initialAgentState)

    const streamUrl = `http://localhost:8000/api/stream?problem=${encodeURIComponent(trimmed)}`
    const source = new EventSource(streamUrl)
    sourceRef.current = source

    source.addEventListener('agent_start', (event) => {
      const payload = JSON.parse(event.data)
      setAgentStates((prev) => ({
        ...prev,
        [payload.agent]: {
          ...prev[payload.agent],
          status: 'active',
          logLine: 'Running…',
        },
      }))
    })

    source.addEventListener('agent_done', (event) => {
      const payload = JSON.parse(event.data)
      const updates = payload.updates || {}
      const logLine = deriveLogLine(payload.agent, updates)

      setAgentStates((prev) => ({
        ...prev,
        [payload.agent]: {
          ...prev[payload.agent],
          status: 'done',
          logLine,
        },
      }))

      setPartialResult((prev) => ({ ...(prev || {}), ...updates }))
    })

    source.addEventListener('complete', (event) => {
      const payload = JSON.parse(event.data)
      setResult(payload.result)
      setStatus('complete')
      source.close()
      sourceRef.current = null
    })

    source.addEventListener('error', (event) => {
      const payload = event?.data ? JSON.parse(event.data) : null
      setError(payload?.message || 'Connection lost during analysis.')
      setStatus('error')
      source.close()
      sourceRef.current = null
    })
  }, [])

  const currentStep = useMemo(() => {
    if (status === 'idle') return 'Problem'
    const active = STEP_ORDER.find((step) => agentStates[step].status === 'active')
    if (!active) {
      if (status === 'complete') return 'Solution'
      return 'Problem'
    }
    if (active === 'analyst') return 'Problem'
    if (active === 'detector') return 'Contradiction'
    if (active === 'solver') return 'Principles'
    return 'Solution'
  }, [agentStates, status])

  return {
    status,
    result,
    partialResult,
    error,
    agentStates,
    currentStep,
    start,
    reset,
  }
}
