import { useEffect, useRef, useState } from 'react'
import Graph from 'graphology'
import { circular } from 'graphology-layout'
import forceAtlas2 from 'graphology-layout-forceatlas2'
import Sigma from 'sigma'
import { api } from './api'
import type { GraphEdge, GraphNode } from './api'
import { labelColor } from './labels'

export interface Selection {
  kind: 'node' | 'edge'
  node?: GraphNode
  edge?: GraphEdge
  noteTitles: Record<string, string>
}

interface GraphViewProps {
  onOpenNote: (id: string) => void
  onSelect: (selection: Selection | null) => void
  at?: string
}

interface LegendEntry {
  label: string
  count: number
  color: string
}

const FADE = '#d0d0d033'

export function GraphView({ onOpenNote, onSelect, at }: GraphViewProps) {
  const container = useRef<HTMLDivElement>(null)
  const [empty, setEmpty] = useState(false)
  const [legend, setLegend] = useState<LegendEntry[]>([])
  const [hasInferred, setHasInferred] = useState(false)
  const hiddenRef = useRef<Set<string>>(new Set())
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  const rendererRef = useRef<Sigma | null>(null)

  useEffect(() => {
    if (!container.current) return
    let renderer: Sigma | null = null
    let cancelled = false
    setEmpty(false)

    Promise.all([api.fullGraph(at), at ? Promise.resolve(null) : api.enrichment().catch(() => null)]).then(
      ([data, enrichment]) => {
        if (cancelled || !container.current) return
        if (data.nodes.length === 0) {
          setEmpty(true)
          return
        }
        const styles = getComputedStyle(document.documentElement)
        const inferredColor = styles.getPropertyValue('--c-org').trim() || '#6e40c9'
        const manualColor = styles.getPropertyValue('--c-wikilink').trim() || '#1f6f61'
        const extractedColor = styles.getPropertyValue('--line').trim() || '#ccc'

        const graph = new Graph({ multi: true })
        const byId = new Map(data.nodes.map((n) => [n.id, n]))
        const byText = new Map(data.nodes.map((n) => [n.text.trim().toLowerCase(), n.id]))

        for (const node of data.nodes) {
          graph.addNode(node.id, {
            label: node.text,
            entityType: node.label,
            color: labelColor(node.label),
            nodeData: node,
          })
        }
        for (const edge of data.edges) {
          if (!graph.hasNode(edge.source) || !graph.hasNode(edge.target)) continue
          graph.addEdge(edge.source, edge.target, {
            label: edge.predicate.replace(/_/g, ' '),
            type: edge.origin === 'extracted' ? 'arrow' : 'line',
            color: edge.origin === 'manual' ? manualColor : extractedColor,
            size: edge.origin === 'manual' ? 2.5 : 1.5,
            edgeData: edge,
          })
        }

        // Inferred connections: a distinct overlay layer (live view only).
        let inferredCount = 0
        for (const inf of enrichment?.inferred ?? []) {
          const src = byText.get(inf.source.trim().toLowerCase())
          const dst = byText.get(inf.target.trim().toLowerCase())
          if (!src || !dst || src === dst) continue
          if (inf.kind === 'bridged') continue // too many to draw legibly
          graph.addEdge(src, dst, {
            label: inf.kind === 'custom' ? inf.because.split('—')[0].trim() : 'inferred',
            type: 'line',
            color: inferredColor + '99',
            size: 1.2,
            inferred: true,
            because: inf.because,
          })
          inferredCount++
        }
        setHasInferred(inferredCount > 0)

        // Node size tracks connectivity.
        graph.forEachNode((id) => {
          const degree = graph.degree(id)
          graph.setNodeAttribute(id, 'size', Math.min(5 + Math.sqrt(degree) * 2.5, 18))
        })

        const counts = new Map<string, number>()
        for (const node of data.nodes) counts.set(node.label, (counts.get(node.label) ?? 0) + 1)
        setLegend(
          Array.from(counts.entries(), ([label, count]) => ({
            label,
            count,
            color: labelColor(label),
          })).sort((a, b) => b.count - a.count),
        )

        circular.assign(graph)
        forceAtlas2.assign(graph, {
          iterations: 300,
          settings: { ...forceAtlas2.inferSettings(graph), gravity: 1.2 },
        })

        let hovered: string | null = null

        renderer = new Sigma(graph, container.current, {
          labelFont: 'system-ui, sans-serif',
          labelSize: 12,
          labelColor: { color: styles.getPropertyValue('--ink').trim() || '#222' },
          renderEdgeLabels: true,
          edgeLabelSize: 10,
          edgeLabelColor: { color: styles.getPropertyValue('--ink-soft').trim() || '#888' },
          enableEdgeEvents: true,
          nodeReducer: (id, attrs) => {
            const res = { ...attrs }
            if (hiddenRef.current.has(attrs.entityType as string)) {
              res.hidden = true
              return res
            }
            if (hovered && id !== hovered && !graph.areNeighbors(id, hovered)) {
              res.color = FADE
              res.label = ''
            }
            return res
          },
          edgeReducer: (id, attrs) => {
            const res = { ...attrs }
            const [src, dst] = graph.extremities(id)
            const srcType = graph.getNodeAttribute(src, 'entityType') as string
            const dstType = graph.getNodeAttribute(dst, 'entityType') as string
            if (hiddenRef.current.has(srcType) || hiddenRef.current.has(dstType)) {
              res.hidden = true
              return res
            }
            if (hovered && src !== hovered && dst !== hovered) {
              res.color = FADE
              res.label = ''
            }
            return res
          },
        })
        rendererRef.current = renderer

        renderer.on('enterNode', ({ node }) => {
          hovered = node
          renderer?.refresh()
        })
        renderer.on('leaveNode', () => {
          hovered = null
          renderer?.refresh()
        })
        renderer.on('clickNode', ({ node }) => {
          const nodeData = byId.get(node)
          if (nodeData) onSelect({ kind: 'node', node: nodeData, noteTitles: data.note_titles })
        })
        renderer.on('clickEdge', ({ edge }) => {
          const edgeData = graph.getEdgeAttribute(edge, 'edgeData') as GraphEdge | undefined
          if (edgeData) onSelect({ kind: 'edge', edge: edgeData, noteTitles: data.note_titles })
        })
        renderer.on('clickStage', () => onSelect(null))
        renderer.on('doubleClickNode', ({ node }) => {
          const nodeData = byId.get(node)
          if (nodeData?.notes.length) onOpenNote(nodeData.notes[0])
        })
      },
    )

    return () => {
      cancelled = true
      renderer?.kill()
      rendererRef.current = null
    }
    // Rebuild on mount and when the snapshot changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [at])

  const toggleType = (label: string) => {
    const next = new Set(hiddenRef.current)
    if (next.has(label)) next.delete(label)
    else next.add(label)
    hiddenRef.current = next
    setHidden(next)
    rendererRef.current?.refresh()
  }

  if (empty) {
    return (
      <div className="placeholder">
        <p>The graph is empty — write some notes first.</p>
      </div>
    )
  }
  return (
    <div className="graph-wrap">
      <div className="graph-canvas" ref={container} />
      <div className="graph-legend">
        {legend.map((entry) => (
          <button
            key={entry.label}
            className={`legend-item ${hidden.has(entry.label) ? 'off' : ''}`}
            title={`Toggle ${entry.label} nodes`}
            onClick={() => toggleType(entry.label)}
          >
            <span className="dot" style={{ background: entry.color }} />
            {entry.label}
            <span className="legend-count">{entry.count}</span>
          </button>
        ))}
        {hasInferred && (
          <span className="legend-item static">
            <span className="legend-line" />
            inferred
          </span>
        )}
      </div>
    </div>
  )
}
