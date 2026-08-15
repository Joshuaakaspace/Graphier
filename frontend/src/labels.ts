const KNOWN: Record<string, string> = {
  PERSON: '--c-person',
  ORG: '--c-org',
  GPE: '--c-gpe',
  DATE: '--c-date',
  CONCEPT: '--c-concept',
  NOTE: '--c-wikilink',
  WIKILINK: '--c-wikilink',
}

// Palette for user-defined domain types — readable on both themes.
const CUSTOM_PALETTE = ['#c2185b', '#00838f', '#7cb342', '#5e35b1', '#ef6c00', '#7d6608']

export function labelColor(label: string): string {
  const varName = KNOWN[label]
  if (varName) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(varName).trim()
    if (value) return value
  }
  let hash = 0
  for (const ch of label) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return CUSTOM_PALETTE[hash % CUSTOM_PALETTE.length]
}
