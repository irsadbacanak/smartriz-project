export default function PrincipleCard({ principle, onExpand }) {
  return (
    <button className="principle-card" onClick={() => onExpand(principle)} type="button">
      <div className="principle-id numeric">P{principle.id}</div>
      <div className="principle-name">{principle.name}</div>
      <p className="principle-description">{principle.description}</p>
      <span className="principle-expand">→</span>
    </button>
  )
}
