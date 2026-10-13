import { ArrowRight, CircleCheckBig, Clock, Download, Eye, Lock, RefreshCw, Trash2, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Button, Field, Input, Modal, Select, cx, errorText, useToast } from '../components/ui'
import { api, type Job } from '../lib/api'
import { ago, bytes, targetLabel, until } from '../lib/format'
import { PRESETS_KB } from './Uploader'

export const qualityTone = (q: string) => (q === 'excellent' || q === 'very good' ? 'green' : q === 'good' ? 'blue' : 'amber')

export function StatusBadge({ job }: { job: Job }) {
  if (job.status === 'done')
    return job.met_target ? (
      <Badge tone="green"><CircleCheckBig className="size-3" /> Fits {targetLabel(job.target_bytes / 1000)}</Badge>
    ) : (
      <Badge tone="amber"><TriangleAlert className="size-3" /> Over limit</Badge>
    )
  if (job.status === 'failed') return <Badge tone="red">Failed</Badge>
  if (job.status === 'expired') return <Badge>Deleted</Badge>
  if (job.status === 'queued') return <Badge tone="blue"><Clock className="size-3" /> Waiting</Badge>
  return <Badge tone="blue">Compressing</Badge>
}

export function RetryModal({ job, open, onClose, onDone }: { job: Job; open: boolean; onClose: () => void; onDone: (j: Job) => void }) {
  const [kb, setKb] = useState(Math.round(job.target_bytes / 1000))
  const [color, setColor] = useState<string>(job.color_mode)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  async function go() {
    setBusy(true)
    try {
      onDone(await api<Job>(`jobs/${job.id}/retry`, { body: { target_kb: kb, color_mode: color } }))
      onClose()
    } catch (e) {
      toast(errorText(e), 'red')
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal open={open} onClose={onClose} title="Compress again">
      <div className="space-y-4">
        <Field label="Size limit">
          <div className="flex flex-wrap gap-2">
            {PRESETS_KB.map((p) => (
              <button key={p} onClick={() => setKb(p)} className={cx('rounded-lg border px-2.5 py-1 text-sm font-semibold', kb === p ? 'border-brand-700 bg-brand-700 text-white' : 'border-slate-300')}>
                {targetLabel(p)}
              </button>
            ))}
            <Input type="number" value={kb} min={20} onChange={(e) => setKb(Number(e.target.value))} className="h-8 w-24" />
          </div>
        </Field>
        <Field label="Colour">
          <Select value={color} onChange={(e) => setColor(e.target.value)}>
            <option value="auto">Automatic</option>
            <option value="color">Keep colour</option>
            <option value="gray">Grayscale</option>
            <option value="bw">Black & white (smallest)</option>
          </Select>
        </Field>
        <p className="text-xs text-slate-500">This doesn’t count as a new document.</p>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={go} loading={busy}>Compress</Button>
        </div>
      </div>
    </Modal>
  )
}

function PasswordRetry({ job, onDone }: { job: Job; onDone: (j: Job) => void }) {
  const [pw, setPw] = useState('')
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  return (
    <form
      className="mt-2 flex flex-wrap items-center gap-2"
      onSubmit={async (e) => {
        e.preventDefault()
        setBusy(true)
        try {
          onDone(await api<Job>(`jobs/${job.id}/retry`, { body: { password: pw } }))
        } catch (err) {
          toast(errorText(err), 'red')
        } finally {
          setBusy(false)
        }
      }}
    >
      <Lock className="size-4 text-slate-400" />
      <Input type="password" placeholder="PDF password" value={pw} onChange={(e) => setPw(e.target.value)} className="h-8 w-44" autoComplete="off" />
      <Button size="sm" type="submit" loading={busy} disabled={!pw}>Unlock</Button>
    </form>
  )
}

export default function JobRow({
  job,
  selected,
  onSelect,
  onChange,
  onDelete,
}: {
  job: Job
  selected: boolean
  onSelect: (v: boolean) => void
  onChange: (j: Job) => void
  onDelete: (id: string) => void
}) {
  const [retry, setRetry] = useState(false)
  const toast = useToast()
  const active = job.status === 'queued' || job.status === 'processing'

  async function remove() {
    if (!confirm(`Delete ${job.display_name}? The files are removed immediately.`)) return
    try {
      await api(`jobs/${job.id}`, { method: 'DELETE' })
      onDelete(job.id)
    } catch (e) {
      toast(errorText(e), 'red')
    }
  }

  return (
    <li className="flex gap-3 px-4 py-4 sm:px-5">
      <input
        type="checkbox"
        className="mt-1 size-4 rounded border-slate-300 accent-brand-700"
        checked={selected}
        disabled={!job.files_available}
        onChange={(e) => onSelect(e.target.checked)}
        aria-label="Select"
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <Link to={`/app/jobs/${job.id}`} className="truncate font-semibold text-slate-900 hover:text-brand-700">{job.display_name}</Link>
          <StatusBadge job={job} />
          {job.status === 'done' && job.text_quality && <Badge tone={qualityTone(job.text_quality)}>Text: {job.text_quality}</Badge>}
        </div>
        <p className="mt-0.5 text-xs text-slate-500">
          {job.label && <span className="font-medium text-slate-700">{job.label} · </span>}
          {job.user_name} · {ago(job.created_at)}
          {job.files_available && <> · deleted {until(job.expires_at)}</>}
        </p>

        {active && (
          <div className="mt-2.5 max-w-md">
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
              <div className="h-full rounded-full bg-brand-600 transition-all duration-700" style={{ width: `${Math.max(4, job.progress * 100)}%` }} />
            </div>
            <p className="mt-1 text-xs text-slate-500">{job.status === 'queued' ? 'Waiting in line…' : job.message || 'Working…'}</p>
          </div>
        )}

        {job.status === 'done' && (
          <p className="mt-1.5 flex flex-wrap items-center gap-2 text-sm">
            <span className="text-slate-400 line-through">{bytes(job.input_bytes)}</span>
            <ArrowRight className="size-3.5 text-slate-400" />
            <span className={cx('font-bold', job.met_target ? 'text-green-700' : 'text-amber-700')}>{bytes(job.output_bytes)}</span>
            {job.ratio && job.ratio > 1.05 && <span className="text-xs text-slate-500">({job.ratio}× smaller)</span>}
            {job.pages && <span className="text-xs text-slate-500">· {job.pages} page{job.pages > 1 ? 's' : ''}</span>}
          </p>
        )}
        {job.status === 'done' && job.warnings.length > 0 && (
          <ul className="mt-1.5 space-y-0.5 text-xs text-amber-800">
            {job.warnings.map((w) => <li key={w}>• {w}</li>)}
          </ul>
        )}
        {job.status === 'failed' && (
          <>
            <p className="mt-1 text-sm text-red-700">{job.error}</p>
            {job.error_code === 'password_required' && <PasswordRetry job={job} onDone={onChange} />}
          </>
        )}
      </div>

      <div className="flex shrink-0 flex-wrap items-start justify-end gap-1.5">
        {job.files_available && (
          <>
            <a href={`/api/jobs/${job.id}/download`} className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-brand-700 px-3 text-sm font-semibold text-white hover:bg-brand-800">
              <Download className="size-4" /> <span className="hidden sm:inline">Download</span>
            </a>
            <Link to={`/app/jobs/${job.id}`} className="inline-flex h-8 items-center rounded-lg border border-slate-300 bg-white px-2.5 text-slate-600 hover:bg-slate-50" title="Compare before / after">
              <Eye className="size-4" />
            </Link>
          </>
        )}
        {(job.status === 'done' || (job.status === 'failed' && job.error_code !== 'password_required')) && (
          <button onClick={() => setRetry(true)} className="inline-flex h-8 items-center rounded-lg border border-slate-300 bg-white px-2.5 text-slate-600 hover:bg-slate-50" title="Compress again with another size">
            <RefreshCw className="size-4" />
          </button>
        )}
        {!active && (
          <button onClick={remove} className="inline-flex h-8 items-center rounded-lg px-2 text-slate-400 hover:bg-red-50 hover:text-red-600" title="Delete">
            <Trash2 className="size-4" />
          </button>
        )}
      </div>
      {retry && <RetryModal job={job} open={retry} onClose={() => setRetry(false)} onDone={onChange} />}
    </li>
  )
}
