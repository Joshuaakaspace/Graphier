import { useEffect, useState } from 'react'
import { api } from './api'
import type { EntityPage } from './api'
import { labelColor } from './labels'

interface EntityViewProps {
  entityId: string
  onOpenNote: (id: string) => void
  onOpenEntity: (id: string) => void
}

export function EntityView({ entityId, onOpenNote, onOpenEntity }: EntityViewProps) {
  const [page, setPage] = useState<EntityPage | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    setPage(null)
    setError(false)
    api.entity(entityId).then(setPage).catch(() => setError(true))
  }, [entityId])

  if (error) return <div className="placeholder"><p>Entity not found.</p></div>
  if (!page) return <div className="placeholder"><p>Loading…</p></div>

  const { node, mentions, relations, inferred, conflicts } = page

  return (
    <div className="entity-page">
      <header className="entity-head">
        <span className="dot" style={{ background: labelColor(node.label) }} />
        <h1>{node.text}</h1>
        <span className="entity-meta">
          {node.label} · {node.count} mention{node.count === 1 ? '' : 's'} ·{' '}
          {node.notes.length} note{node.notes.length === 1 ? '' : 's'}
        </span>
      </header>

      {mentions.length > 0 && (
        <section>
          <h2>Mentions</h2>
          <ul className="evidence-list">
            {mentions.map((m, i) => (
              <li key={i}>
                <blockquote>“{m.sentence}”</blockquote>
                <button className="link-btn" onClick={() => onOpenNote(m.note)}>
                  {m.title ?? m.note}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {relations.length > 0 && (
        <section>
          <h2>Relations</h2>
          <ul className="evidence-list">
            {relations.map((r, i) => (
              <li key={i}>
                <div className="relation-line">
                  {r.direction === 'out' ? (
                    <>
                      <strong>{node.text}</strong>
                      <span className="rel-pred"> {r.predicate.replace(/_/g, ' ')} </span>
                      <button className="link-btn" onClick={() => onOpenEntity(r.other_id)}>
                        {r.other}
                      </button>
                    </>
                  ) : (
                    <>
                      <button className="link-btn" onClick={() => onOpenEntity(r.other_id)}>
                        {r.other}
                      </button>
                      <span className="rel-pred"> {r.predicate.replace(/_/g, ' ')} </span>
                      <strong>{node.text}</strong>
                    </>
                  )}
                  <span className="entity-meta">
                    {' '}
                    · {r.origin === 'manual' ? 'wiki-link' : `${(r.confidence * 100).toFixed(0)}%`}
                  </span>
                </div>
                {r.evidence[0] && (
                  <blockquote>
                    “{r.evidence[0].sentence}”
                    <button
                      className="link-btn"
                      onClick={() => onOpenNote(r.evidence[0].note)}
                    >
                      — {r.evidence[0].title ?? r.evidence[0].note}
                    </button>
                  </blockquote>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {conflicts.length > 0 && (
        <section>
          <h2 className="conflict-h">Conflicts</h2>
          <ul className="evidence-list">
            {conflicts.map((c, i) => (
              <li key={i}>
                <div className="relation-line">
                  <strong>{c.subject}</strong>
                  <span className="rel-pred"> {c.predicate}</span>
                </div>
                {c.claims.map((claim) => (
                  <blockquote key={claim.object}>
                    {claim.object}
                    {' — '}
                    {claim.notes.map((n) => (
                      <button
                        key={n.id}
                        className="link-btn"
                        onClick={() => onOpenNote(n.id)}
                      >
                        {n.title}
                      </button>
                    ))}
                  </blockquote>
                ))}
              </li>
            ))}
          </ul>
        </section>
      )}

      {inferred.length > 0 && (
        <section>
          <h2>Inferred</h2>
          <ul className="evidence-list">
            {inferred.map((inf, i) => (
              <li key={i}>
                <div className="relation-line">
                  <strong>{inf.source}</strong>
                  <span className="rel-pred"> ↔ </span>
                  <strong>{inf.target}</strong>
                </div>
                <blockquote>{inf.because}</blockquote>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
