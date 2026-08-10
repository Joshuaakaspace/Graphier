import { useEffect, useRef } from 'react'
import { EditorView, Decoration, keymap } from '@codemirror/view'
import type { DecorationSet } from '@codemirror/view'
import { EditorState, StateEffect, StateField } from '@codemirror/state'
import { markdown } from '@codemirror/lang-markdown'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import type { Extraction } from './api'

const setHighlights = StateEffect.define<DecorationSet>()

const highlightField = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(value, tr) {
    for (const e of tr.effects) if (e.is(setHighlights)) return e.value
    return value.map(tr.changes)
  },
  provide: (f) => EditorView.decorations.from(f),
})

function buildDecorations(extraction: Extraction, docLength: number): DecorationSet {
  const marks = []
  for (const ent of extraction.entities) {
    if (ent.end > docLength || ent.start >= ent.end) continue
    marks.push(
      Decoration.mark({
        class: `ent ent-${ent.label}`,
        attributes: { title: `${ent.label} · ${(ent.confidence * 100).toFixed(0)}%` },
      }).range(ent.start, ent.end),
    )
  }
  for (const link of extraction.wikilinks) {
    if (link.end > docLength || link.start >= link.end) continue
    marks.push(
      Decoration.mark({
        class: 'ent ent-WIKILINK',
        attributes: { title: 'wiki-link (manual edge)' },
      }).range(link.start, link.end),
    )
  }
  marks.sort((a, b) => a.from - b.from || a.to - b.to)
  return Decoration.set(marks, true)
}

interface EditorProps {
  noteId: string
  initialContent: string
  extraction: Extraction | null
  onChange: (content: string) => void
}

export function Editor({ noteId, initialContent, extraction, onChange }: EditorProps) {
  const container = useRef<HTMLDivElement>(null)
  const view = useRef<EditorView | null>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  useEffect(() => {
    if (!container.current) return
    const state = EditorState.create({
      doc: initialContent,
      extensions: [
        history(),
        keymap.of([...defaultKeymap, ...historyKeymap]),
        markdown(),
        highlightField,
        EditorView.lineWrapping,
        EditorView.updateListener.of((update) => {
          if (update.docChanged) onChangeRef.current(update.state.doc.toString())
        }),
      ],
    })
    view.current = new EditorView({ state, parent: container.current })
    return () => {
      view.current?.destroy()
      view.current = null
    }
    // Recreate the editor only when switching notes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [noteId])

  useEffect(() => {
    if (!view.current || !extraction) return
    const decorations = buildDecorations(extraction, view.current.state.doc.length)
    view.current.dispatch({ effects: setHighlights.of(decorations) })
  }, [extraction])

  return <div className="editor" ref={container} />
}
