export interface NoteMeta {
  id: string
  title: string
  modified: number
  size: number
}

export interface Entity {
  text: string
  label: string
  start: number
  end: number
  confidence: number
}

export interface WikiLink {
  text: string
  start: number
  end: number
}

export interface Relation {
  subject: string
  subject_label: string
  predicate: string
  object: string
  object_label: string
  confidence: number
}

export interface Extraction {
  entities: Entity[]
  wikilinks: WikiLink[]
  relations: Relation[]
}

export interface GraphSummary {
  notes: number
  nodes: number
  edges: number
  by_label: Record<string, number>
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  listNotes: () => fetch('/api/notes').then((r) => json<NoteMeta[]>(r)),
  createNote: (title: string) =>
    fetch('/api/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    }).then((r) => json<{ id: string }>(r)),
  readNote: (id: string) =>
    fetch(`/api/notes/${id}`).then((r) => json<{ id: string; content: string }>(r)),
  saveNote: (id: string, content: string) =>
    fetch(`/api/notes/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    }).then((r) => json<{ id: string }>(r)),
  deleteNote: (id: string) => fetch(`/api/notes/${id}`, { method: 'DELETE' }),
  entities: (id: string) =>
    fetch(`/api/notes/${id}/entities`).then((r) => json<Extraction>(r)),
  graph: () =>
    fetch('/api/graph').then((r) => json<{ summary: GraphSummary }>(r)),
}
