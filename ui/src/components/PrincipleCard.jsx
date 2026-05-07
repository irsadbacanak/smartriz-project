export default function PrincipleCard({ principle, onExpand, application }) {
  return (
    <button className="principle-card" onClick={() => onExpand(principle)} type="button">
      <div className="principle-id numeric">P{principle.id}</div>
      <div className="principle-name">{principle.name}</div>
      <p className="principle-description">{principle.description}</p>
      {application ? (
        <div className="principle-application">
          <span className="application-label">Applied here as:</span>
          <p>{application}</p>
        </div>
      ) : null}
      <span className="principle-expand">→ Detail</span>
    </button>
  )
}
