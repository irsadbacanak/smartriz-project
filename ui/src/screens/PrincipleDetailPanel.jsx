import CaseCard from '../components/CaseCard'

export default function PrincipleDetailPanel({ principle, cases, onApply, onClose }) {
  if (!principle) return null

  const hasCases = cases && cases.length > 0

  return (
    <aside className="detail-panel">
      <div className="panel-header">
        <h3>
          <span className="numeric">P{principle.id}</span> {principle.name}
        </h3>
        <button className="text-button" onClick={onClose} type="button">
          Close
        </button>
      </div>

      <ol className="subprinciple-list">
        {principle.sub_principles?.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
      </ol>

      {hasCases ? (
        <>
          <div className="cases-title">Cases from knowledge base</div>
          <div className="cases-column">
            {cases.slice(0, 3).map((item) => (
              <CaseCard key={item.id} item={item} />
            ))}
          </div>
        </>
      ) : null}

      <button className="primary-button panel-button" type="button" onClick={() => onApply(principle)}>
        Apply this principle →
      </button>
    </aside>
  )
}
