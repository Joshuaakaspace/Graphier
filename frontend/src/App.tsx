import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import type {
  Enrichment,
  Extraction,
  GraphSummary,
  NoteMeta,
  QueryResult,
  SearchResponse,
  Snapshot,
  Suggestion,
} from './api'
import { Editor } from './Editor'
import { EntityView } from './EntityView'
import { labelColor } from './labels'
import { GraphView } from './GraphView'
import type { Selection } from './GraphView'
import './App.css'

const nodeKey = (text: string, label: string) => `${label}:${text.trim().toLowerCase()}`

const QUERY_BLOCK_RE = /```query\s*\n([\s\S]*?)```/g

function parseQueries(content: string): string[] {
  const queries: string[] = []
  for (const match of content.matchAll(QUERY_BLOCK_RE)) {
    for (const line of match[1].split('\n')) {
      const q = line.trim()
      if (q && !q.startsWith('%')) queries.push(q)
    }
  }
  return queries
}

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
  const [activeKind, setActiveKind] = useState<string>('md')
  const [content, setContent] = useState<string>('')
  const [extraction, setExtraction] = useState<Extraction | null>(null)
  const [summary, setSummary] = useState<GraphSummary | null>(null)
  const [enrichment, setEnrichment] = useState<Enrichment | null>(null)
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [status, setStatus] = useState<'saved' | 'saving' | 'extracting'>('saved')
  const [view, setView] = useState<'editor' | 'graph' | 'entity'>('editor')
  const [entityId, setEntityId] = useState<string | null>(null)
  const [selection, setSelection] = useState<Selection | null>(null)
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null)
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [atSnapshot, setAtSnapshot] = useState<string>('')
  const [queryResults, setQueryResults] = useState<Record<string, QueryResult | null>>({})
  const saveTimer = useRef<number | undefined>(undefined)
  const searchTimer = useRef<number | undefined>(undefined)

  const refreshNotes = useCallback(() => api.listNotes().then(setNotes), [])
  const refreshSummary = useCallback(
    () => api.graph().then((g) => setSummary(g.summary)).catch(() => {}),
    [],
  )
  const refreshEnrichment = useCallback(
    () => api.enrichment().then(setEnrichment).catch(() => {}),
    [],
  )
  const refreshSnapshots = useCallback(
    () => api.history().then((h) => setSnapshots(h.snapshots)).catch(() => {}),
    [],
  )

  useEffect(() => {
    refreshNotes()
    refreshSummary()
    refreshEnrichment()
    refreshSnapshots()
  }, [refreshNotes, refreshSummary, refreshEnrichment, refreshSnapshots])

  const openNote = useCallback((id: string) => {
    api.readNote(id).then((note) => {
      setView('editor')
      setSelection(null)
      setActiveId(id)
      setActiveKind(note.kind ?? 'md')
      setContent(note.content)
      setExtraction(null)
      setSuggestions([])
      api.entities(id).then(setExtraction).catch(() => {})
      api.suggestions(id).then((s) => setSuggestions(s.suggestions)).catch(() => {})
    })
  }, [])

  const openEntity = useCallback((id: string) => {
    setEntityId(id)
    setView('entity')
    setSelection(null)
  }, [])

  const handleSearch = useCallback((text: string) => {
    setQuery(text)
    window.clearTimeout(searchTimer.current)
    if (!text.trim()) {
      setSearchResults(null)
      return
    }
    searchTimer.current = window.setTimeout(() => {
      api.search(text).then(setSearchResults).catch(() => {})
    }, 300)
  }, [])

  const takeSnapshot = useCallback(() => {
    api.snapshot('snapshot').then((res) => {
      if (!res.created) window.alert('Nothing changed since the last snapshot.')
      refreshSnapshots()
    })
  }, [refreshSnapshots])

  const acceptSuggestion = useCallback(
    (text: string) => {
      if (!activeId) return
      api.readNote(activeId).then((note) => {
        const idx = note.content.indexOf(text)
        if (idx < 0 || note.content.slice(idx - 2, idx) === '[[') return
        const linked =
          note.content.slice(0, idx) + `[[${text}]]` + note.content.slice(idx + text.length)
        api.saveNote(activeId, linked).then(() => openNote(activeId))
      })
    },
    [activeId, openNote],
  )

  const uploadPdf = useCallback(
    (file: File) => {
      api
        .uploadDocument(file)
        .then(({ id }) => {
          refreshNotes()
          refreshSummary()
          openNote(id)
        })
        .catch(() => window.alert('Could not extract text from that document.'))
    },
    [openNote, refreshNotes, refreshSummary],
  )

  const handleChange = useCallback(
    (text: string) => {
      if (!activeId) return
      setContent(text)
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

  // Live queries: ```query blocks in the open note re-run after each save.
  useEffect(() => {
    const queries = parseQueries(content)
    if (queries.length === 0) {
      setQueryResults({})
      return
    }
    let cancelled = false
    Promise.all(
      queries.map((q) =>
        api
          .query(q)
          .then((res) => [q, res] as const)
          .catch(() => [q, null] as const),
      ),
    ).then((pairs) => {
      if (!cancelled) setQueryResults(Object.fromEntries(pairs))
    })
    return () => {
      cancelled = true
    }
  }, [content, extraction])

  const grouped = groupEntities(extraction)
  const liveQueries = Object.entries(queryResults)

  return (
    <div className="app">
      <aside className="sidebar">
        <header className="sidebar-head">
          <h1>Graphier</h1>
          <span className="head-actions">
            <label className="btn-upload" title="Add a document (PDF, TXT, HTML, DOCX)">
              + Doc
              <input
                type="file"
                accept=".pdf,.txt,.html,.htm,.docx"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) uploadPdf(file)
                  e.target.value = ''
                }}
              />
            </label>
            <button className="btn-new" onClick={createNote}>
              + Note
            </button>
          </span>
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
        <input
          className="search-box"
          type="search"
          placeholder="Search the vault…"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
        />
        {query.trim() && searchResults ? (
          <nav className="note-list search-results">
            {searchResults.entities.length > 0 && (
              <div className="entity-hits">
                {searchResults.entities.map((e) => (
                  <button
                    key={e.id}
                    className={`entity-chip chip-${e.label}`}
                    onClick={() => openEntity(e.id)}
                  >
                    {e.text}
                  </button>
                ))}
              </div>
            )}
            {searchResults.results.map((hit) => (
              <div key={hit.id} className="note-item search-hit" onClick={() => openNote(hit.id)}>
                <div>
                  <span className="note-title">{hit.title}</span>
                  <div className="snippet">{hit.snippet}</div>
                </div>
              </div>
            ))}
            {searchResults.results.length === 0 && <p className="empty">No matches.</p>}
          </nav>
        ) : (
        <nav className="note-list">
          {notes.map((n) => (
            <div
              key={n.id}
              className={`note-item ${n.id === activeId ? 'active' : ''}`}
              onClick={() => openNote(n.id)}
            >
              <span className="note-title">{n.title}</span>
              {n.kind !== 'md' && <span className="pdf-badge">{n.kind.toUpperCase()}</span>}
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
        )}
        {summary && (
          <footer className="graph-summary">
            <span>{summary.notes} notes</span>
            <span>{summary.nodes} nodes</span>
            <span>{summary.edges} edges</span>
          </footer>
        )}
      </aside>

      <main className="main">
        {view === 'entity' && entityId ? (
          <>
            <div className="editor-head">
              <button className="link-btn" onClick={() => setView(activeId ? 'editor' : 'graph')}>
                ← back
              </button>
              <span className="note-id">entity</span>
            </div>
            <EntityView entityId={entityId} onOpenNote={openNote} onOpenEntity={openEntity} />
          </>
        ) : view === 'graph' ? (
          <>
            <div className="editor-head">
              <span className="note-id">
                vault graph{atSnapshot ? ` @ ${atSnapshot}` : ''}
              </span>
              <span className="timeline">
                <select
                  value={atSnapshot}
                  onChange={(e) => {
                    setAtSnapshot(e.target.value)
                    setSelection(null)
                  }}
                >
                  <option value="">Live</option>
                  {snapshots.map((s) => (
                    <option key={s.sha} value={s.sha}>
                      {new Date(s.timestamp * 1000).toLocaleString()} · {s.message}
                    </option>
                  ))}
                </select>
                <button className="btn-new" onClick={takeSnapshot}>
                  Snapshot
                </button>
              </span>
            </div>
            <GraphView
              key={atSnapshot}
              at={atSnapshot || undefined}
              onOpenNote={openNote}
              onSelect={setSelection}
            />
          </>
        ) : activeId ? (
          <>
            <div className="editor-head">
              <span className="note-id">
                {activeId}.{activeKind}
              </span>
              {activeKind !== 'md' ? (
                <span className="status">extracted text · read-only</span>
              ) : (
                <span className={`status status-${status}`}>
                  {status === 'saved' ? 'Saved' : status === 'saving' ? 'Saving…' : 'Extracting…'}
                </span>
              )}
            </div>
            <Editor
              noteId={activeId}
              initialContent={content}
              extraction={extraction}
              onChange={handleChange}
              readOnly={activeKind !== 'md'}
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
                  <span className="dot" style={{ background: labelColor(selection.node.label) }} />
                  {selection.node.text}
                </h3>
                <p className="selection-meta">
                  {selection.node.label} · {selection.node.count} mention
                  {selection.node.count === 1 ? '' : 's'}
                </p>
                <button
                  className="btn-new"
                  onClick={() => openEntity(selection.node!.id)}
                >
                  Open entity page
                </button>
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
                {selection.edge.evidence.map((ev, i) => (
                  <blockquote className="evidence-quote" key={i}>
                    “{ev.sentence}”
                    <button className="link-btn" onClick={() => openNote(ev.note)}>
                      — {selection.noteTitles[ev.note] ?? ev.note}
                    </button>
                  </blockquote>
                ))}
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
              <span className="dot" style={{ background: labelColor(label) }} />
              {LABEL_NAMES[label] ?? label}
              <span className="count">{items.length}</span>
            </h3>
            <ul>
              {items.map((text) => (
                <li key={text}>
                  {label === 'WIKILINK' ? (
                    text
                  ) : (
                    <button className="link-btn" onClick={() => openEntity(nodeKey(text, label))}>
                      {text}
                    </button>
                  )}
                </li>
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
                <li key={s.text} className="suggestion-row">
                  <span>
                    <span className="rel-entity">{s.text}</span>
                    <span className="suggest-notes">
                      {' — '}
                      {s.also_in.map((n) => n.title).join(', ')}
                    </span>
                  </span>
                  {activeKind === 'md' && (
                    <button
                      className="btn-accept"
                      title={`Wrap "${s.text}" in a wiki-link`}
                      onClick={() => acceptSuggestion(s.text)}
                    >
                      + Link
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        {view === 'editor' && liveQueries.length > 0 && (
          <section className="entity-group">
            <h3>
              <span className="dot dot-QUERY" />
              Live queries
              <span className="count">{liveQueries.length}</span>
            </h3>
            {liveQueries.map(([q, res]) => (
              <div className="live-query" key={q}>
                <code>{q}</code>
                {res === null && <p className="empty">query error</p>}
                {res && res.rows.length === 0 && <p className="empty">no results</p>}
                {res && res.kind === 'entities' && (
                  <ul>
                    {res.rows.map((row, i) => (
                      <li key={i}>
                        <button
                          className="link-btn"
                          onClick={() => openEntity(String(row.id))}
                        >
                          {String(row.text)}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {res && res.kind === 'relations' && (
                  <ul>
                    {res.rows.map((row, i) => (
                      <li key={i}>
                        <span className="rel-entity">{String(row.source)}</span>
                        <span className="rel-pred"> {String(row.predicate).replace(/_/g, ' ')} </span>
                        <span className="rel-entity">{String(row.target)}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {res && res.kind === 'connected' && (
                  <ul>
                    {res.rows.map((row, i) => (
                      <li key={i}>
                        <span className="rel-entity">{String(row.text)}</span>
                        <span className="rel-pred"> {String(row.predicate).replace(/_/g, ' ')}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {res && res.kind === 'datalog' && (
                  <ul>
                    {res.rows.map((row, i) => (
                      <li key={i}>
                        {Object.entries(row).map(([k, v], j) => (
                          <span key={k}>
                            {j > 0 && <span className="rel-pred"> · </span>}
                            <span className="suggest-notes">{k} = </span>
                            <span className="rel-entity">{String(v)}</span>
                          </span>
                        ))}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
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
                        <button
                          className="link-btn"
                          onClick={() => openEntity(nodeKey(ins.text, ins.label))}
                        >
                          {ins.text}
                        </button>
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
