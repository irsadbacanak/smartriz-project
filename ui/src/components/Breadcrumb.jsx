const STEPS = ['Problem', 'Contradiction', 'Principles', 'Solution']

export default function Breadcrumb({ currentStep }) {
  return (
    <nav className="breadcrumb" aria-label="analysis-steps">
      {STEPS.map((step, idx) => (
        <span key={step} className={`crumb ${step === currentStep ? 'active' : ''}`}>
          {step}
          {idx < STEPS.length - 1 ? <span className="divider">→</span> : null}
        </span>
      ))}
    </nav>
  )
}
