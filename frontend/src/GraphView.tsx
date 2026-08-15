import { useEffect, useRef, useState } from 'react'
import Graph from 'graphology'
import { circular } from 'graphology-layout'
import forceAtlas2 from 'graphology-layout-forceatlas2'
import Sigma from 'sigma'
import { api } from './api'
import type { FullGraph, GraphEdge, GraphNode } from './api'
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

export function GraphView({ onOpenNote, onSelect, at }: GraphViewProps) {
  const container = useRef<HTMLDivElement>(null)
  const [empty, setEmpty] = useState(false)

  useEffect(() => {
    if (!container.current) return
    let renderer: Sigma | null = null
    let cancelled = false
    setEmpty(false)

    api.fullGraph(at).then((data: FullGraph) => {
      if (cancelled || !container.current) return
      if (data.nodes.length === 0) {
        setEmpty(true)
        return
      }
      const styles = getComputedStyle(document.documentElement)
      const colorOf = labelColor

      const graph = new Graph({ multi: true })
      const byId = new Map(data.nodes.map((n) => [n.id, n]))

      for (const node of data.nodes) {
        graph.addNode(node.id, {
          label: node.text,
          color: colorOf(node.label),
          size: Math.min(6 + node.count * 2.5, 18),
          nodeData: node,
        })
      }
      for (const edge of data.edges) {
        if (!graph.hasNode(edge.source) || !graph.hasNode(edge.target)) continue
        graph.addEdge(edge.source, edge.target, {
          color: edge.origin === 'manual' ? colorOf('NOTE') : styles.getPropertyValue('--line').trim(),
          size: edge.origin === 'manual' ? 2.5 : 1.5,
          edgeData: edge,
        })
      }

      circular.assign(graph)
      forceAtlas2.assign(graph, {
        iterations: 300,
        settings: { ...forceAtlas2.inferSettings(graph), gravity: 1.2 },
      })

      renderer = new Sigma(graph, container.current, {
        labelFont: 'system-ui, sans-serif',
        labelSize: 12,
        labelColor: { color: styles.getPropertyValue('--ink').trim() || '#222' },
        renderEdgeLabels: false,
        enableEdgeEvents: true,
      })

      renderer.on('clickNode', ({ node }) => {
        const nodeData = byId.get(node)
        if (nodeData) onSelect({ kind: 'node', node: nodeData, noteTitles: data.note_titles })
      })
      renderer.on('clickEdge', ({ edge }) => {
        const edgeData = graph.getEdgeAttribute(edge, 'edgeData') as GraphEdge
        if (edgeData) onSelect({ kind: 'edge', edge: edgeData, noteTitles: data.note_titles })
      })
      renderer.on('clickStage', () => onSelect(null))
      renderer.on('doubleClickNode', ({ node }) => {
        const nodeData = byId.get(node)
        if (nodeData?.notes.length) onOpenNote(nodeData.notes[0])
      })
    })

    return () => {
      cancelled = true
      renderer?.kill()
    }
    // Rebuild on mount and when the snapshot changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [at])

  if (empty) {
    return (
      <div className="placeholder">
        <p>The graph is empty — write some notes first.</p>
      </div>
    )
  }
  return <div className="graph-canvas" ref={container} />
}
