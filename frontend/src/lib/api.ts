// Thin fetch wrapper for the Django API (session cookie + CSRF header).

export class ApiError extends Error {
  status: number
  code?: string
  errors?: Record<string, unknown>
  constructor(message: string, status: number, errors?: Record<string, unknown>) {
    super(message)
    this.status = status
    this.errors = errors
  }
}

function cookie(name: string): string {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return m ? decodeURIComponent(m[1]) : ''
}

let csrfReady: Promise<unknown> | null = null
export function ensureCsrf() {
  if (!cookie('csrftoken')) csrfReady ??= fetch('/api/auth/csrf', { credentials: 'same-origin' })
  return csrfReady ?? Promise.resolve()
}

export async function api<T = unknown>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const method = opts.method ?? (opts.body ? 'POST' : 'GET')
  const headers: Record<string, string> = { Accept: 'application/json' }
  let body: BodyInit | undefined
  if (opts.body instanceof FormData) body = opts.body
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.body)
  }
  if (method !== 'GET') {
    await ensureCsrf()
    headers['X-CSRFToken'] = cookie('csrftoken')
  }
  const res = await fetch('/api/' + path, { method, headers, body, credentials: 'same-origin' })
  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const msg = typeof data.detail === 'string' ? data.detail : `Request failed (${res.status})`
    throw new ApiError(msg, res.status, data.errors)
  }
  return data as T
}

/** Upload with progress (fetch has no upload progress events). */
export function upload<T>(path: string, form: FormData, onProgress: (frac: number) => void): Promise<T> {
  return ensureCsrf().then(
    () =>
      new Promise<T>((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.open('POST', '/api/' + path)
        xhr.setRequestHeader('X-CSRFToken', cookie('csrftoken'))
        xhr.setRequestHeader('Accept', 'application/json')
        xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total)
        xhr.onload = () => {
          let data: { detail?: string; errors?: Record<string, unknown> } = {}
          try {
            data = JSON.parse(xhr.responseText)
          } catch {
            /* non-JSON error page */
          }
          if (xhr.status >= 200 && xhr.status < 300) resolve(data as T)
          else if (xhr.status === 413) reject(new ApiError('These files are too large to upload.', 413))
          else reject(new ApiError(data.detail ?? `Upload failed (${xhr.status})`, xhr.status, data.errors))
        }
        xhr.onerror = () => reject(new ApiError('Network error. Check your internet connection.', 0))
        xhr.send(form)
      }),
  )
}

// ---- types

export interface Plan {
  code: string
  name: string
  price_npr: number
  monthly_docs: number
  max_upload_mb: number
  max_pages: number
  seats: number
  retention_hours: number
  api_access: boolean
}

export interface User {
  id: number
  email: string
  full_name: string
  role: 'owner' | 'admin' | 'member'
  date_joined: string
  last_login: string | null
}

export interface Me {
  user: User
  organization: { id: number; name: string; phone: string; default_target_kb: number }
  plan: Plan
  plan_expires_at: string | null
  usage: { used: number; limit: number; period_start: string }
  payments_enabled: boolean
}

export type JobStatus = 'queued' | 'processing' | 'done' | 'failed' | 'expired'

export interface Job {
  id: string
  display_name: string
  label: string
  input_names: string[]
  input_bytes: number
  target_bytes: number
  color_mode: 'auto' | 'color' | 'gray' | 'bw'
  output_format: 'pdf' | 'jpg'
  clean_background: boolean
  status: JobStatus
  progress: number
  message: string
  error: string
  error_code: string
  output_name: string
  output_bytes: number | null
  pages: number | null
  met_target: boolean | null
  text_quality: string
  warnings: string[]
  ratio: number | null
  files_available: boolean
  user_name: string
  via_api: boolean
  created_at: string
  finished_at: string | null
  expires_at: string
}

export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
