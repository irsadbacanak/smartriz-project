import ParameterChip from '../components/ParameterChip'
import PrincipleCard from '../components/PrincipleCard'

export default function ContradictionMatrix({
  parameters,
  improvingId,
  worseningId,
  matrixMap,
  recommendedPrinciples,
  onExpandPrinciple,
}) {
  const key = `${improvingId}-${worseningId}`
  const highlightedIds = matrixMap[key] || []

  return (
    <section className="matrix-screen">
      <div className="chip-row">
        <ParameterChip label={`${parameters[improvingId - 1]?.name || 'Unknown'} `} trend="up" />
        <span className="chip-conflict">conflicts with</span>
        <ParameterChip label={`${parameters[worseningId - 1]?.name || 'Unknown'} `} trend="down" />
      </div>

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

      <div className="principle-strip">
        {recommendedPrinciples.map((principle) => (
          <PrincipleCard key={principle.id} principle={principle} onExpand={onExpandPrinciple} />
        ))}
      </div>
    </section>
  )
}
