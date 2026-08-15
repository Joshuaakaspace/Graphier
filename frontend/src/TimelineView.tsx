import { useEffect, useState } from 'react'
import { api } from './api'
import type { TimelineEvent } from './api'
import { labelColor } from './labels'

interface TimelineViewProps {
  onOpenNote: (id: string) => void
  onOpenEntity: (id: string) => void
}

const nodeKey = (text: string, label: string) => `${label}:${text.trim().toLowerCase()}`

export function TimelineView({ onOpenNote, onOpenEntity }: TimelineViewProps) {
  const [events, setEvents] = useState<TimelineEvent[] | null>(null)

  useEffect(() => {
    api.timeline().then((r) => setEvents(r.events)).catch(() => setEvents([]))
  }, [])

  if (events === null) return <div className="placeholder"><p>Loading…</p></div>
  if (events.length === 0) {
    return (
      <div className="placeholder">
        <p>No dated events yet — mention a date in a note or document.</p>
      </div>
    )
  }

  let lastYear: number | null = null

  return (
    <div className="timeline-view">
      {events.map((event, i) => {
        const yearHeader = event.year !== lastYear
        lastYear = event.year
        return (
          <div key={i}>
            {yearHeader && <h2 className="timeline-year">{event.year}</h2>}
            <div className="timeline-event">
              <span className="timeline-date">{event.date}</span>
              <div className="timeline-card">
                <blockquote>“{event.sentence}”</blockquote>
                <div className="timeline-meta">
                  <button className="link-btn" onClick={() => onOpenNote(event.note)}>
                    {event.title}
                  </button>
                  {event.kind !== 'md' && (
                    <span className="pdf-badge">{event.kind.toUpperCase()}</span>
                  )}
                  <span className="timeline-cast">
                    {event.entities.map((e) => (
                      <button
                        key={e.text}
                        className="cast-chip"
                        style={{ borderColor: labelColor(e.label) }}
                        onClick={() => onOpenEntity(nodeKey(e.text, e.label))}
                      >
                        {e.text}
                      </button>
                    ))}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
