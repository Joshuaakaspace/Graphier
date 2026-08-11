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

export interface InferredConnection {
  kind: 'chained' | 'bridged' | 'custom'
  source: string
  target: string
  because: string
}

export interface ConflictClaim {
  object: string
  notes: { id: string; title: string }[]
}

export interface Conflict {
  subject: string
  predicate: string
  claims: ConflictClaim[]
}

export interface Insight {
  text: string
  label: string
  score: number
}

export interface Enrichment {
  inferred: InferredConnection[]
  conflicts: Conflict[]
  insights: Insight[]
}

export interface Suggestion {
  text: string
  label: string
  also_in: { id: string; title: string }[]
}

export interface Evidence {
  note: string
  sentence: string
  title?: string
}

export interface GraphNode {
  id: string
  text: string
  label: string
  count: number
  notes: string[]
  evidence: Evidence[]
}

export interface GraphEdge {
  source: string
  target: string
  predicate: string
  origin: 'extracted' | 'manual'
  confidence: number
  notes: string[]
  evidence: Evidence[]
}

export interface EntityRelation {
  predicate: string
  direction: 'in' | 'out'
  other: string
  other_id: string
  origin: 'extracted' | 'manual'
  confidence: number
  evidence: Evidence[]
}

export interface EntityPage {
  node: GraphNode
  mentions: Evidence[]
  relations: EntityRelation[]
  inferred: InferredConnection[]
  conflicts: Conflict[]
}

export interface FullGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  note_titles: Record<string, string>
  summary: GraphSummary
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
  fullGraph: () => fetch('/api/graph').then((r) => json<FullGraph>(r)),
  entity: (id: string) =>
    fetch(`/api/entity?id=${encodeURIComponent(id)}`).then((r) => json<EntityPage>(r)),
  enrichment: () => fetch('/api/enrichment').then((r) => json<Enrichment>(r)),
  suggestions: (id: string) =>
    fetch(`/api/notes/${id}/suggestions`).then((r) =>
      json<{ suggestions: Suggestion[] }>(r),
    ),
}
