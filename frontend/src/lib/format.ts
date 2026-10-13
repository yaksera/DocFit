/** Sizes use decimal units (1 MB = 1,000,000 bytes), the stricter reading of portal limits. */
export function bytes(n: number | null | undefined): string {
  if (n == null) return '–'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)} MB`
  if (n >= 1000) return `${Math.round(n / 1000)} KB`
  return `${n} B`
}

export function targetLabel(kb: number): string {
  return kb >= 1000 ? `${+(kb / 1000).toFixed(1)} MB` : `${kb} KB`
}

export function npr(n: number): string {
  return 'NPR ' + n.toLocaleString('en-IN')
}

export function ago(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export function until(iso: string): string {
  const s = (new Date(iso).getTime() - Date.now()) / 1000
  if (s <= 0) return 'now'
  if (s < 3600) return `in ${Math.max(1, Math.floor(s / 60))} min`
  if (s < 86400) return `in ${Math.floor(s / 3600)} h`
  return `in ${Math.floor(s / 86400)} days`
}

export function date(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}
