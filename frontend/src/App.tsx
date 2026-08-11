import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import type { Enrichment, Extraction, GraphSummary, NoteMeta, Suggestion } from './api'
import { Editor } from './Editor'
import { GraphView } from './GraphView'
import type { Selection } from './GraphView'
import './App.css'

const LABEL_NAMES: Record<string, string> = {
  PERSON: 'People',
  ORG: 'Organizations',
  GPE: 'Places',
  DATE: 'Dates',
  CONCEPT: 'Concepts',
  WIKILINK: 'Wiki-links',
}

export default function App() {
  const [notes, setNotes] = useState<NoteMeta[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [content, setContent] = useState<string>('')
  const [extraction, setExtraction] = useState<Extraction | null>(null)
  const [summary, setSummary] = useState<GraphSummary | null>(null)
  const [enrichment, setEnrichment] = useState<Enrichment | null>(null)
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [status, setStatus] = useState<'saved' | 'saving' | 'extracting'>('saved')
  const [view, setView] = useState<'editor' | 'graph'>('editor')
  const [selection, setSelection] = useState<Selection | null>(null)
  const saveTimer = useRef<number | undefined>(undefined)

  const refreshNotes = useCallback(() => api.listNotes().then(setNotes), [])
  const refreshSummary = useCallback(
    () => api.graph().then((g) => setSummary(g.summary)).catch(() => {}),
    [],
  )
  const refreshEnrichment = useCallback(
    () => api.enrichment().then(setEnrichment).catch(() => {}),
    [],
  )

  useEffect(() => {
    refreshNotes()
    refreshSummary()
    refreshEnrichment()
  }, [refreshNotes, refreshSummary, refreshEnrichment])

  const openNote = useCallback((id: string) => {
    api.readNote(id).then((note) => {
      setView('editor')
      setSelection(null)
      setActiveId(id)
      setContent(note.content)
      setExtraction(null)
      setSuggestions([])
      api.entities(id).then(setExtraction).catch(() => {})
      api.suggestions(id).then((s) => setSuggestions(s.suggestions)).catch(() => {})
    })
  }, [])

  const handleChange = useCallback(
    (text: string) => {
      if (!activeId) return
      setStatus('saving')
      window.clearTimeout(saveTimer.current)
      saveTimer.current = window.setTimeout(() => {
        api
          .saveNote(activeId, text)
          .then(() => {
            setStatus('extracting')
            return api.entities(activeId)
          })
          .then((ex) => {
            setExtraction(ex)
            setStatus('saved')
            refreshNotes()
            refreshSummary()
            refreshEnrichment()
            api.suggestions(activeId).then((s) => setSuggestions(s.suggestions)).catch(() => {})
          })
          .catch(() => setStatus('saved'))
      }, 600)
    },
    [activeId, refreshNotes, refreshSummary, refreshEnrichment],
  )

  const createNote = useCallback(() => {
    const title = window.prompt('Note title')
    if (!title) return
    api.createNote(title).then(({ id }) => {
      refreshNotes()
      openNote(id)
    })
  }, [openNote, refreshNotes])

  const deleteNote = useCallback(
    (id: string) => {
      if (!window.confirm('Delete this note?')) return
      api.deleteNote(id).then(() => {
        refreshNotes()
        refreshSummary()
        if (activeId === id) {
          setActiveId(null)
          setExtraction(null)
        }
      })
    },
    [activeId, refreshNotes, refreshSummary],
  )

  const grouped = groupEntities(extraction)

  return (
    <div className="app">
      <aside className="sidebar">
        <header className="sidebar-head">
          <h1>Graphier</h1>
          <button className="btn-new" onClick={createNote}>
            + Note
          </button>
        </header>
        <div className="view-toggle">
          <button
            className={view === 'editor' ? 'active' : ''}
            onClick={() => setView('editor')}
          >
            Notes
          </button>
          <button
            className={view === 'graph' ? 'active' : ''}
            onClick={() => {
              setView('graph')
              setSelection(null)
            }}
          >
            Graph
          </button>
        </div>
        <nav className="note-list">
          {notes.map((n) => (
            <div
              key={n.id}
              className={`note-item ${n.id === activeId ? 'active' : ''}`}
              onClick={() => openNote(n.id)}
            >
              <span className="note-title">{n.title}</span>
              <button
                className="btn-delete"
                title="Delete note"
                onClick={(e) => {
                  e.stopPropagation()
                  deleteNote(n.id)
                }}
              >
                ×
              </button>
            </div>
          ))}
          {notes.length === 0 && <p className="empty">No notes yet.</p>}
        </nav>
        {summary && (
          <footer className="graph-summary">
            <span>{summary.notes} notes</span>
            <span>{summary.nodes} nodes</span>
            <span>{summary.edges} edges</span>
          </footer>
        )}
      </aside>

      <main className="main">
        {view === 'graph' ? (
          <>
            <div className="editor-head">
              <span className="note-id">vault graph</span>
              <span className="status">
                double-click a node to open its note · click an edge for provenance
              </span>
            </div>
            <GraphView onOpenNote={openNote} onSelect={setSelection} />
          </>
        ) : activeId ? (
          <>
            <div className="editor-head">
              <span className="note-id">{activeId}.md</span>
              <span className={`status status-${status}`}>
                {status === 'saved' ? 'Saved' : status === 'saving' ? 'Saving…' : 'Extracting…'}
              </span>
            </div>
            <Editor
              noteId={activeId}
              initialContent={content}
              extraction={extraction}
              onChange={handleChange}
            />
          </>
        ) : (
          <div className="placeholder">
            <p>Select a note, or create one.</p>
            <p className="hint">
              Entities light up as you write — people, organizations, places, dates — and
              every note feeds the vault's knowledge graph.
            </p>
          </div>
        )}
      </main>

      <aside className="panel">
        {view === 'graph' && (
          <section className="selection-card">
            <h2>Selection</h2>
            {!selection && <p className="empty">Click a node or an edge.</p>}
            {selection?.kind === 'node' && selection.node && (
              <>
                <h3>
                  <span className={`dot dot-${selection.node.label}`} />
                  {selection.node.text}
                </h3>
                <p className="selection-meta">
                  {selection.node.label} · {selection.node.count} mention
                  {selection.node.count === 1 ? '' : 's'}
                </p>
                <ul>
                  {selection.node.notes.map((id) => (
                    <li key={id}>
                      <button className="link-btn" onClick={() => openNote(id)}>
                        {selection.noteTitles[id] ?? id}
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {selection?.kind === 'edge' && selection.edge && (
              <>
                <h3>
                  <span className="dot dot-REL" />
                  {selection.edge.predicate.replace(/_/g, ' ')}
                </h3>
                <p className="selection-meta">
                  {selection.edge.origin === 'manual'
                    ? 'manual wiki-link'
                    : `extracted · ${(selection.edge.confidence * 100).toFixed(0)}% confidence`}
                </p>
                <p className="selection-meta">Appears in:</p>
                <ul>
                  {selection.edge.notes.map((id) => (
                    <li key={id}>
                      <button className="link-btn" onClick={() => openNote(id)}>
                        {selection.noteTitles[id] ?? id}
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>
        )}
        {view === 'editor' && <h2>In this note</h2>}
        {view === 'editor' && grouped.length === 0 && (
          <p className="empty">Nothing extracted yet.</p>
        )}
        {view === 'editor' &&
        grouped.map(([label, items]) => (
          <section key={label} className="entity-group">
            <h3>
              <span className={`dot dot-${label}`} />
              {LABEL_NAMES[label] ?? label}
              <span className="count">{items.length}</span>
            </h3>
            <ul>
              {items.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          </section>
        ))}
        {view === 'editor' && extraction && extraction.relations.length > 0 && (
          <section className="entity-group">
            <h3>
              <span className="dot dot-REL" />
              Relations
              <span className="count">{extraction.relations.length}</span>
            </h3>
            <ul className="relations">
              {extraction.relations.map((r, i) => (
                <li key={i}>
                  <span className="rel-entity">{r.subject}</span>
                  <span className="rel-pred"> {r.predicate.replace(/_/g, ' ')} </span>
                  <span className="rel-entity">{r.object}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {view === 'editor' && activeId && suggestions.length > 0 && (
          <section className="entity-group">
            <h3>
              <span className="dot dot-SUGGEST" />
              Also mentioned in
              <span className="count">{suggestions.length}</span>
            </h3>
            <ul className="suggestions">
              {suggestions.map((s) => (
                <li key={s.text}>
                  <span className="rel-entity">{s.text}</span>
                  <span className="suggest-notes">
                    {' — '}
                    {s.also_in.map((n) => n.title).join(', ')}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {enrichment && (
          <>
            <h2 className="vault-head">Vault intelligence</h2>

            {enrichment.insights.length > 0 && (
              <section className="entity-group">
                <h3>
                  <span className="dot dot-INSIGHT" />
                  Central entities
                </h3>
                <ul className="insights">
                  {enrichment.insights.map((ins) => {
                    const max = enrichment.insights[0].score || 1
                    return (
                      <li key={ins.text}>
                        <span className="rel-entity">{ins.text}</span>
                        <span
                          className="insight-bar"
                          style={{ width: `${Math.max(8, (ins.score / max) * 60)}px` }}
                        />
                      </li>
                    )
                  })}
                </ul>
              </section>
            )}

            {enrichment.inferred.length > 0 && (
              <section className="entity-group">
                <h3>
                  <span className="dot dot-INFERRED" />
                  Inferred connections
                  <span className="count">{enrichment.inferred.length}</span>
                </h3>
                <ul className="inferred">
                  {enrichment.inferred.slice(0, 6).map((inf, i) => (
                    <li key={i}>
                      <div>
                        <span className="rel-entity">{inf.source}</span>
                        <span className="rel-pred"> ↔ </span>
                        <span className="rel-entity">{inf.target}</span>
                      </div>
                      <div className="because">{inf.because}</div>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {enrichment.conflicts.length > 0 && (
              <section className="entity-group">
                <h3>
                  <span className="dot dot-CONFLICT" />
                  Conflicts
                  <span className="count">{enrichment.conflicts.length}</span>
                </h3>
                <ul className="conflicts">
                  {enrichment.conflicts.map((c, i) => (
                    <li key={i}>
                      <div>
                        <span className="rel-entity">{c.subject}</span>
                        <span className="rel-pred"> {c.predicate} </span>
                      </div>
                      {c.claims.map((claim) => (
                        <div className="claim" key={claim.object}>
                          {claim.object}
                          <span className="suggest-notes">
                            {' '}
                            ({claim.notes.map((n) => n.title).join(', ')})
                          </span>
                        </div>
                      ))}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}
      </aside>
    </div>
  )
}

function groupEntities(extraction: Extraction | null): [string, string[]][] {
  if (!extraction) return []
  const groups = new Map<string, Set<string>>()
  for (const e of extraction.entities) {
    if (!groups.has(e.label)) groups.set(e.label, new Set())
    groups.get(e.label)!.add(e.text)
  }
  if (extraction.wikilinks.length > 0) {
    groups.set('WIKILINK', new Set(extraction.wikilinks.map((w) => w.text)))
  }
  return Array.from(groups.entries(), ([label, set]) => [label, Array.from(set)] as [string, string[]])
}
