import SimilarityBar from './SimilarityBar'

export default function CaseCard({ item }) {
  return (
    <article className="case-card">
      <div className="case-head">
        <span className="case-domain">{item.domain}</span>
      </div>
      <p className="case-summary">{item.summary}</p>
      <SimilarityBar value={item.similarity} />
    </article>
  )
}
