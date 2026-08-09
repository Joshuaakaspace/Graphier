import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import type { Extraction, GraphSummary, NoteMeta } from './api'
import { Editor } from './Editor'
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
  const [status, setStatus] = useState<'saved' | 'saving' | 'extracting'>('saved')
  const saveTimer = useRef<number | undefined>(undefined)

  const refreshNotes = useCallback(() => api.listNotes().then(setNotes), [])
  const refreshSummary = useCallback(
    () => api.graph().then((g) => setSummary(g.summary)).catch(() => {}),
    [],
  )

  useEffect(() => {
    refreshNotes()
    refreshSummary()
  }, [refreshNotes, refreshSummary])

  const openNote = useCallback((id: string) => {
    api.readNote(id).then((note) => {
      setActiveId(id)
      setContent(note.content)
      setExtraction(null)
      api.entities(id).then(setExtraction).catch(() => {})
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
          })
          .catch(() => setStatus('saved'))
      }, 600)
    },
    [activeId, refreshNotes, refreshSummary],
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
        {activeId ? (
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
        <h2>In this note</h2>
        {grouped.length === 0 && <p className="empty">Nothing extracted yet.</p>}
        {grouped.map(([label, items]) => (
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
        {extraction && extraction.relations.length > 0 && (
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
