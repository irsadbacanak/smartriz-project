export function ActionsFooter({ onRefine }) {
  return (
    <footer className="actions-footer">
      <button type="button" className="primary-button" onClick={onRefine}>
        Refine Problem →
      </button>
      <button type="button" className="outline-button" disabled title="Export coming soon">
        Export Report
      </button>
    </footer>
  )
}
