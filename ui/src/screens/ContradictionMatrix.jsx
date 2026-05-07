import { useState } from 'react'
import ParameterChip from '../components/ParameterChip'

export default function ContradictionMatrix({
  parameters,
  improvingId,
  worseningId,
  matrixMap,
}) {
  const [showFull, setShowFull] = useState(false)
  const key = `${improvingId}-${worseningId}`
  const highlightedIds = matrixMap[key] || []
  const improvingParam = parameters[improvingId - 1]
  const worseningParam = parameters[worseningId - 1]

  return (
    <details className="reference-matrix-details">
      <summary className="text-button">Reference: TRIZ-39 contradiction matrix</summary>

      <div className="reference-matrix-body">
        <div className="reference-matrix-cell">
          <div className="ref-cell-header">
            <ParameterChip label={`#${improvingId} ${improvingParam?.name || ''}`} trend="up" />
            <span className="chip-conflict">×</span>
            <ParameterChip label={`#${worseningId} ${worseningParam?.name || ''}`} trend="down" />
          </div>
          <div className="ref-cell-content">
            <span className="ref-cell-label">Model selected:</span>
            <span className="ref-cell-value">
              {highlightedIds.length > 0
                ? highlightedIds.map((id) => `P${id}`).join(' · ')
                : 'principles from model output above'}
            </span>
          </div>
          <div className="ref-cell-content">
            <span className="ref-cell-label">TRIZ-39 matrix suggests:</span>
            <span className="ref-cell-value">
              {highlightedIds.length > 0
                ? highlightedIds.map((id) => `P${id}`).join(', ')
                : '— (local model did not query matrix)'}
            </span>
          </div>
        </div>

        <button
          className="text-button ref-expand-btn"
          type="button"
          onClick={() => setShowFull((v) => !v)}
        >
          {showFull ? 'Collapse full matrix ↑' : 'Open full 39×39 matrix →'}
        </button>

        {showFull ? (
          <div className="matrix-wrapper">
            <table className="triz-matrix">
              <thead>
                <tr>
                  <th className="sticky-header sticky-corner">#</th>
                  {parameters.map((parameter) => (
                    <th
                      key={parameter.id}
                      className={`sticky-header ${parameter.id === worseningId ? 'worsening-col' : ''}`}
                    >
                      <span className="numeric">{parameter.id}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {parameters.map((row) => (
                  <tr key={row.id}>
                    <th className={`sticky-side ${row.id === improvingId ? 'improving-row' : ''}`}>
                      <span className="numeric">{row.id}</span>
                    </th>
                    {parameters.map((col) => {
                      const cellKey = `${row.id}-${col.id}`
                      const active = cellKey === key && highlightedIds.length > 0
                      return (
                        <td key={cellKey} className={active ? 'matrix-hit' : ''}>
                          {active ? highlightedIds.slice(0, 3).join(', ') : ''}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </details>
  )
}
