import { useState } from 'react'
import './App.css'

const API_URL = 'http://localhost:8000/api/analyze'

function StatusBadge({ text }) {
  const approved = text?.toLowerCase() === 'approved'
  return (
    <span className={`badge ${approved ? 'badge-approved' : 'badge-pending'}`}>
      {text ?? '—'}
    </span>
  )
}

function ResultSection({ title, children }) {
  return (
    <section className="result-section">
      <h3 className="result-title">{title}</h3>
      {children}
    </section>
  )
}

export default function App() {
  const [problem, setProblem] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleAnalyze = async () => {
    if (!problem.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ problem }),
      })
      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${response.status}`)
      }
      setResult(await response.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleAnalyze()
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>SmarTRIZ</h1>
        <p className="subtitle">Multi-Agent TRIZ Analysis System</p>
      </header>

      <main className="app-main">
        <div className="input-card">
          <label htmlFor="problem" className="input-label">
            Engineering Problem
          </label>
          <textarea
            id="problem"
            className="input-textarea"
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g. We need to make the aircraft wing stronger, but adding material makes it too heavy."
            rows={5}
          />
          <div className="input-hint">Tip: Cmd+Enter / Ctrl+Enter to run</div>
          <button
            className="run-button"
            onClick={handleAnalyze}
            disabled={loading || !problem.trim()}
          >
            {loading ? (
              <span className="spinner-row">
                <span className="spinner" /> Agents are working...
              </span>
            ) : (
              'Run TRIZ Analysis'
            )}
          </button>
        </div>

        {error && (
          <div className="alert alert-error">
            <strong>Error:</strong> {error}
          </div>
        )}

        {result && (
          <div className="results-card">
            <ResultSection title="1. Problem Analysis">
              <p className="result-text">{result.analysis ?? '—'}</p>
            </ResultSection>

            <ResultSection title="2. Detected Contradictions">
              {result.contradictions?.length ? (
                <ul className="contradiction-list">
                  {result.contradictions.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              ) : (
                <p className="result-text muted">No contradictions detected.</p>
              )}
            </ResultSection>

            <ResultSection title="3. Proposed Solution">
              <p className="result-text">{result.final_solution ?? '—'}</p>
            </ResultSection>

            <ResultSection title="4. Critic Feedback">
              <div className="critic-row">
                <StatusBadge text={result.critic_feedback} />
                <span className="iteration-tag">
                  Iteration {result.iterations ?? 0}
                </span>
              </div>
            </ResultSection>
          </div>
        )}
      </main>
    </div>
  )
}
