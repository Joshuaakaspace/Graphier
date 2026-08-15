import { useMemo, useState } from 'react'
import type { TimelineEvent } from './api'
import { labelColor } from './labels'

interface LifelineChartProps {
  events: TimelineEvent[]
  onOpenEntity: (id: string) => void
  onJumpTo: (eventIndex: number) => void
}

const nodeKey = (text: string, label: string) => `${label}:${text.trim().toLowerCase()}`

const GUTTER = 138
const ROW_H = 30
const WIDTH = 820
const AXIS_H = 26
const MAX_ROWS = 7

interface Row {
  text: string
  label: string
  points: { t: number; eventIndex: number }[]
}

interface Hover {
  x: number
  y: number
  event: TimelineEvent
}

function timeOf(event: TimelineEvent): number {
  const [y, m, d] = event.sort_key
  return y + (m > 0 ? (m - 1) / 12 : 0.5) + (d > 0 ? d / 372 : 0)
}

export function LifelineChart({ events, onOpenEntity, onJumpTo }: LifelineChartProps) {
  const [hover, setHover] = useState<Hover | null>(null)

  const { rows, minT, maxT, ticks } = useMemo(() => {
    const byEntity = new Map<string, Row>()
    events.forEach((event, eventIndex) => {
      const t = timeOf(event)
      for (const ent of event.entities) {
        const key = `${ent.label}:${ent.text}`
        if (!byEntity.has(key)) byEntity.set(key, { text: ent.text, label: ent.label, points: [] })
        byEntity.get(key)!.points.push({ t, eventIndex })
      }
    })
    const rows = Array.from(byEntity.values())
      .sort((a, b) => b.points.length - a.points.length || a.text.localeCompare(b.text))
      .slice(0, MAX_ROWS)
      .sort((a, b) => a.points[0].t - b.points[0].t)

    const times = events.map(timeOf)
    let lo = Math.min(...times)
    let hi = Math.max(...times)
    if (hi - lo < 1) {
      lo -= 1
      hi += 1
    }
    const pad = (hi - lo) * 0.04
    lo -= pad
    hi += pad
    const span = hi - lo
    const step = Math.max(1, Math.ceil(span / 8))
    const ticks: number[] = []
    for (let y = Math.ceil(lo); y <= Math.floor(hi); y += step) ticks.push(y)
    return { rows, minT: lo, maxT: hi, ticks }
  }, [events])

  if (rows.length === 0) return null

  const x = (t: number) => GUTTER + ((t - minT) / (maxT - minT)) * (WIDTH - GUTTER - 16)
  const height = rows.length * ROW_H + AXIS_H

  return (
    <div className="lifeline-wrap">
      <svg
        viewBox={`0 0 ${WIDTH} ${height}`}
        className="lifeline-chart"
        role="img"
        aria-label="Entity lifelines over time"
      >
        {ticks.map((year) => (
          <g key={year}>
            <line
              className="tl-grid"
              x1={x(year)}
              x2={x(year)}
              y1={4}
              y2={height - AXIS_H + 6}
            />
            <text className="tl-tick" x={x(year)} y={height - 8} textAnchor="middle">
              {year}
            </text>
          </g>
        ))}
        {rows.map((row, i) => {
          const cy = i * ROW_H + ROW_H / 2 + 2
          const color = labelColor(row.label)
          const first = x(row.points[0].t)
          const last = x(row.points[row.points.length - 1].t)
          return (
            <g key={`${row.label}:${row.text}`}>
              <text
                className="tl-name"
                x={GUTTER - 10}
                y={cy + 4}
                textAnchor="end"
                onClick={() => onOpenEntity(nodeKey(row.text, row.label))}
              >
                {row.text.length > 18 ? row.text.slice(0, 17) + '…' : row.text}
              </text>
              {row.points.length > 1 && (
                <line className="tl-life" x1={first} x2={last} y1={cy} y2={cy} stroke={color} />
              )}
              {row.points.map((p, j) => (
                <g key={j}>
                  <circle cx={x(p.t)} cy={cy} r={5} fill={color} className="tl-dot" />
                  <circle
                    cx={x(p.t)}
                    cy={cy}
                    r={10}
                    fill="transparent"
                    className="tl-hit"
                    onMouseEnter={() =>
                      setHover({ x: x(p.t), y: cy, event: events[p.eventIndex] })
                    }
                    onMouseLeave={() => setHover(null)}
                    onClick={() => onJumpTo(p.eventIndex)}
                  />
                </g>
              ))}
            </g>
          )
        })}
      </svg>
      {hover && (
        <div
          className="tl-tooltip"
          style={{
            left: `${Math.min(78, Math.max(20, (hover.x / WIDTH) * 100))}%`,
            top: hover.y + 18,
          }}
        >
          <strong>{hover.event.date}</strong> · {hover.event.title}
          <div className="tl-tooltip-sentence">
            {hover.event.sentence.length > 110
              ? hover.event.sentence.slice(0, 108) + '…'
              : hover.event.sentence}
          </div>
        </div>
      )}
    </div>
  )
}
