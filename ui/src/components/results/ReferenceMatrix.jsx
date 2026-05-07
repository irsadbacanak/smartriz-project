function range(start, end) {
  const arr = []
  for (let i = start; i <= end; i++) arr.push(i)
  return arr
}

export function ReferenceMatrix({ parameters, improvingId, worseningId, matrixMap, principleIds }) {
  if (!improvingId || !worseningId) return null

  const rowMin = Math.max(1, improvingId - 3)
  const rowMax = Math.min(39, improvingId + 3)
  const colMin = Math.max(1, worseningId - 3)
  const colMax = Math.min(39, worseningId + 3)

  const rowRange = range(rowMin, rowMax)
  const colRange = range(colMin, colMax)

  return (
    <details className="reference-matrix">
      <summary>View contradiction matrix lookup</summary>
      <div className="mini-matrix-wrapper">
        <table className="mini-matrix">
          <thead>
            <tr>
              <th></th>
              {colRange.map(c => (
                <th key={c} className={c === worseningId ? 'axis-highlight' : ''}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rowRange.map(r => (
              <tr key={r}>
                <th className={r === improvingId ? 'axis-highlight' : ''}>{r}</th>
                {colRange.map(c => {
                  const key = `${r}-${c}`
                  const cell = matrixMap[key]
                  const isTarget = r === improvingId && c === worseningId
                  return (
                    <td key={c} className={isTarget ? 'highlighted' : ''}>
                      {cell ? cell.join(', ') : '—'}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="matrix-note">
          Highlighted: improving #{improvingId} × worsening #{worseningId}
        </p>
      </div>
    </details>
  )
}
