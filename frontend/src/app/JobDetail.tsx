import { ArrowLeft, ChevronLeft, ChevronRight, Download, RefreshCw, ZoomIn, ZoomOut } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Alert, Badge, Button, Spinner, errorText } from '../components/ui'
import { api, type Job } from '../lib/api'
import { bytes, date, targetLabel, until } from '../lib/format'
import { RetryModal, StatusBadge, qualityTone } from './JobRow'

const ZOOMS = [1, 1.5, 2, 3]

function Pane({ src, label, sub, paneRef, onScroll, zoom }: {
  src: string
  label: string
  sub: string
  paneRef: React.RefObject<HTMLDivElement | null>
  onScroll: () => void
  zoom: number
}) {
  const [loaded, setLoaded] = useState(false)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    setLoaded(false)
    setFailed(false)
  }, [src])
  return (
    <div className="card flex min-w-0 flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2.5">
        <span className="font-semibold text-slate-900">{label}</span>
        <span className="text-sm text-slate-500">{sub}</span>
      </div>
      <div ref={paneRef} onScroll={onScroll} className="checker relative h-[70vh] overflow-auto">
        {!loaded && !failed && (
          <div className="absolute inset-0 flex items-center justify-center"><Spinner /></div>
        )}
        {failed ? (
          <p className="p-6 text-center text-sm text-slate-500">Preview not available.</p>
        ) : (
          <img
            src={src}
            alt={label}
            onLoad={() => setLoaded(true)}
            onError={() => setFailed(true)}
            style={{ width: `${zoom * 100}%`, maxWidth: 'none' }}
            className="block bg-white shadow"
            draggable={false}
          />
        )}
      </div>
    </div>
  )
}

export default function JobDetail() {
  const { id = '' } = useParams()
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)
  const [zoom, setZoom] = useState(1)
  const [retry, setRetry] = useState(false)
  const left = useRef<HTMLDivElement>(null)
  const right = useRef<HTMLDivElement>(null)
  const syncing = useRef(false)

  useEffect(() => {
    api<Job>(`jobs/${id}`).then(setJob, (e) => setError(errorText(e)))
  }, [id])

  // Keep polling while the job is running (also after "Another size").
  const active = job?.status === 'queued' || job?.status === 'processing'
  useEffect(() => {
    if (!active) return
    const t = setInterval(() => api<Job>(`jobs/${id}`).then(setJob).catch(() => {}), 1500)
    return () => clearInterval(t)
  }, [active, id])

  // Scroll both panes together so the same spot is compared.
  const sync = (from: React.RefObject<HTMLDivElement | null>, to: React.RefObject<HTMLDivElement | null>) => () => {
    if (syncing.current || !from.current || !to.current) return
    syncing.current = true
    const f = from.current
    const t = to.current
    t.scrollTop = (f.scrollTop / Math.max(1, f.scrollHeight - f.clientHeight)) * (t.scrollHeight - t.clientHeight)
    t.scrollLeft = (f.scrollLeft / Math.max(1, f.scrollWidth - f.clientWidth)) * (t.scrollWidth - t.clientWidth)
    requestAnimationFrame(() => (syncing.current = false))
  }

  if (error) return <Alert>{error}</Alert>
  if (!job) return <div className="flex justify-center py-20"><Spinner /></div>

  const width = Math.min(1800, Math.round(800 * zoom))
  const v = job.finished_at ?? ''
  const pages = job.pages ?? 1

  return (
    <>
      <Link to="/app" className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-900">
        <ArrowLeft className="size-4" /> All documents
      </Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-bold tracking-tight text-slate-900">{job.display_name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-500">
            <StatusBadge job={job} />
            {job.text_quality && <Badge tone={qualityTone(job.text_quality)}>Text: {job.text_quality}</Badge>}
            {job.label && <span className="font-medium text-slate-700">{job.label}</span>}
            <span>· {date(job.created_at)}</span>
            {job.files_available && <span>· files deleted {until(job.expires_at)}</span>}
          </div>
        </div>
        {job.files_available && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setRetry(true)}><RefreshCw className="size-4" /> Another size</Button>
            <a href={`/api/jobs/${job.id}/download`} className="inline-flex h-10 items-center gap-2 rounded-lg bg-brand-700 px-4 text-sm font-semibold text-white hover:bg-brand-800">
              <Download className="size-4" /> Download {bytes(job.output_bytes)}
            </a>
          </div>
        )}
      </div>

      {job.status === 'failed' && <Alert>{job.error}</Alert>}
      {job.status === 'expired' && <Alert tone="amber">The files were deleted automatically for privacy. Upload the document again to compress it.</Alert>}
      {(job.status === 'queued' || job.status === 'processing') && (
        <div className="card p-6">
          <p className="font-medium text-slate-700">{job.message || 'Waiting in line…'}</p>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
            <div className="h-full bg-brand-600 transition-all duration-700" style={{ width: `${Math.max(4, job.progress * 100)}%` }} />
          </div>
        </div>
      )}

      {job.status === 'done' && (
        <>
          {job.warnings.length > 0 && (
            <div className="mb-4">
              <Alert tone="amber">
                {job.warnings.map((w) => <p key={w}>{w}</p>)}
              </Alert>
            </div>
          )}
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Previous page"><ChevronLeft className="size-4" /></Button>
              <span className="text-sm text-slate-600">Page {page} of {pages}</span>
              <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label="Next page"><ChevronRight className="size-4" /></Button>
            </div>
            <div className="flex items-center gap-2">
              <span className="hidden text-sm text-slate-500 sm:inline">Zoom in to check small print</span>
              <Button size="sm" variant="secondary" disabled={zoom === ZOOMS[0]} onClick={() => setZoom(ZOOMS[ZOOMS.indexOf(zoom) - 1])} aria-label="Zoom out"><ZoomOut className="size-4" /></Button>
              <span className="w-12 text-center text-sm font-semibold">{zoom * 100}%</span>
              <Button size="sm" variant="secondary" disabled={zoom === ZOOMS[ZOOMS.length - 1]} onClick={() => setZoom(ZOOMS[ZOOMS.indexOf(zoom) + 1])} aria-label="Zoom in"><ZoomIn className="size-4" /></Button>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Pane label="Original" sub={bytes(job.input_bytes)} zoom={zoom} paneRef={left} onScroll={sync(left, right)}
              src={`/api/jobs/${job.id}/preview/before?page=${page}&width=${width}`} />
            <Pane label="Compressed" sub={`${bytes(job.output_bytes)} · limit ${targetLabel(job.target_bytes / 1000)}`} zoom={zoom} paneRef={right} onScroll={sync(right, left)}
              src={`/api/jobs/${job.id}/preview/after?page=${page}&width=${width}&v=${encodeURIComponent(v)}`} />
          </div>
        </>
      )}
      {retry && <RetryModal job={job} open={retry} onClose={() => setRetry(false)} onDone={setJob} />}
    </>
  )
}
