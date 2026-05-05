import { useCallback, useMemo, useRef, useState } from 'react'

const STEP_ORDER = ['analyst', 'detector', 'solver', 'critic']

const initialAgentState = {
  analyst: { status: 'waiting', logLine: 'Waiting for input.' },
  detector: { status: 'waiting', logLine: 'Waiting for upstream output.' },
  solver: { status: 'waiting', logLine: 'Waiting for contradiction mapping.' },
  critic: { status: 'waiting', logLine: 'Waiting for candidate solution.' },
}

export function useTrizStream() {
  const [status, setStatus] = useState('idle')
  const [result, setResult] = useState(null)
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
          logLine: 'Running...',
        },
      }))
    })

    source.addEventListener('agent_done', (event) => {
      const payload = JSON.parse(event.data)
      setAgentStates((prev) => ({
        ...prev,
        [payload.agent]: {
          ...prev[payload.agent],
          status: 'done',
          logLine: payload.log_line || 'Step complete.',
        },
      }))
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
    error,
    agentStates,
    currentStep,
    start,
    reset,
  }
}
