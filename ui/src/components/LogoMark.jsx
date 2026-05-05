export default function LogoMark() {
  return (
    <div className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 24 24" className="logo-grid">
        <rect x="2" y="2" width="8" height="8" className="filled" />
        <rect x="14" y="2" width="8" height="8" className="outlined" />
        <rect x="2" y="14" width="8" height="8" className="outlined" />
        <rect x="14" y="14" width="8" height="8" className="filled" />
      </svg>
    </div>
  )
}
