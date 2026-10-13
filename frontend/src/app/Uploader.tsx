import { ArrowDown, ArrowUp, FileText, Image as ImageIcon, Lock, Upload, X } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'
import { Alert, Button, Field, Input, Select, Toggle, cx, errorText, useToast } from '../components/ui'
import { upload, type Job } from '../lib/api'
import { useAuth, useMe } from '../lib/auth'
import { bytes, targetLabel } from '../lib/format'

export const PRESETS_KB = [4000, 2000, 1000, 500, 300, 200, 100]
const ACCEPT = '.pdf,.jpg,.jpeg,.png,.heic,.heif,.webp,.tif,.tiff,.bmp'

export default function Uploader({ onCreated }: { onCreated: (jobs: Job[]) => void }) {
  const me = useMe()
  const { refresh } = useAuth()
  const toast = useToast()
  const input = useRef<HTMLInputElement>(null)
  const [files, setFiles] = useState<File[]>([])
  const [drag, setDrag] = useState(false)
  const [targetKb, setTargetKb] = useState(me.organization.default_target_kb)
  const [custom, setCustom] = useState(!PRESETS_KB.includes(me.organization.default_target_kb))
  const [format, setFormat] = useState<'pdf' | 'jpg'>('pdf')
  const [color, setColor] = useState('auto')
  const [merge, setMerge] = useState(false)
  const [clean, setClean] = useState(true)
  const [label, setLabel] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState('')

  const total = files.reduce((s, f) => s + f.size, 0)
  const maxBytes = me.plan.max_upload_mb * 1024 * 1024

  function add(list: FileList | null) {
    if (!list) return
    setError('')
    setFiles((prev) => [...prev, ...Array.from(list)].slice(0, 50))
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDrag(false)
    add(e.dataTransfer.files)
  }

  function move(i: number, d: number) {
    setFiles((f) => {
      const n = [...f]
      ;[n[i], n[i + d]] = [n[i + d], n[i]]
      return n
    })
  }

  async function submit() {
    if (!files.length) return
    const merging = merge && files.length > 1
    if ((merging || files.length === 1 ? total : Math.max(...files.map((f) => f.size))) > maxBytes) {
      setError(`Your ${me.plan.name} plan accepts up to ${me.plan.max_upload_mb} MB per job.`)
      return
    }
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    form.append('target_kb', String(targetKb))
    form.append('output_format', format)
    form.append('color_mode', color)
    form.append('merge', String(merging))
    form.append('clean_background', String(clean))
    if (label) form.append('label', label)
    if (password) form.append('password', password)
    setError('')
    setProgress(0)
    try {
      const jobs = await upload<Job[]>('jobs', form, setProgress)
      onCreated(jobs)
      toast(jobs.length === 1 ? 'Uploaded. Compressing now…' : `${jobs.length} files uploaded. Compressing now…`)
      setFiles([])
      setPassword('')
      setShowPassword(false)
      refresh()
    } catch (e) {
      setError(errorText(e))
    } finally {
      setProgress(null)
    }
  }

  return (
    <div className="card overflow-hidden">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDrag(true)
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        onClick={() => input.current?.click()}
        className={cx(
          'm-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors',
          drag ? 'border-brand-600 bg-brand-50' : 'border-slate-300 hover:border-brand-500 hover:bg-slate-50',
        )}
      >
        <div className="flex size-12 items-center justify-center rounded-full bg-brand-100 text-brand-700">
          <Upload className="size-6" />
        </div>
        <p className="mt-3 font-semibold text-slate-900">Drop documents here or click to choose</p>
        <p className="mt-1 text-sm text-slate-500">PDF, JPG, PNG, HEIC (iPhone), WebP, TIFF · up to {me.plan.max_upload_mb} MB per job</p>
        <input ref={input} type="file" multiple accept={ACCEPT} className="hidden" onChange={(e) => {
          add(e.target.files)
          e.target.value = ''
        }} />
      </div>

      {files.length > 0 && (
        <div className="border-t border-slate-200 px-4 py-4 sm:px-6">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-semibold text-slate-700">
              {files.length} file{files.length > 1 ? 's' : ''} · {bytes(total)}
            </span>
            <button className="text-slate-500 hover:text-slate-800" onClick={() => setFiles([])}>Clear</button>
          </div>
          <ul className="max-h-56 divide-y divide-slate-100 overflow-auto rounded-lg border border-slate-200">
            {files.map((f, i) => (
              <li key={i + f.name} className="flex items-center gap-3 px-3 py-2 text-sm">
                {f.type.startsWith('image/') ? <ImageIcon className="size-4 shrink-0 text-slate-400" /> : <FileText className="size-4 shrink-0 text-red-500" />}
                <span className="min-w-0 flex-1 truncate text-slate-800">{f.name}</span>
                <span className="text-xs text-slate-500">{bytes(f.size)}</span>
                {merge && files.length > 1 && (
                  <span className="flex">
                    <button disabled={i === 0} onClick={() => move(i, -1)} className="rounded p-1 text-slate-400 hover:text-slate-800 disabled:opacity-30" aria-label="Move up"><ArrowUp className="size-3.5" /></button>
                    <button disabled={i === files.length - 1} onClick={() => move(i, 1)} className="rounded p-1 text-slate-400 hover:text-slate-800 disabled:opacity-30" aria-label="Move down"><ArrowDown className="size-3.5" /></button>
                  </span>
                )}
                <button onClick={() => setFiles(files.filter((_, j) => j !== i))} className="rounded p-1 text-slate-400 hover:text-red-600" aria-label="Remove">
                  <X className="size-4" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="space-y-5 border-t border-slate-200 bg-slate-50/60 px-4 py-5 sm:px-6">
        <div>
          <span className="mb-2 block text-sm font-medium text-slate-700">Size limit of the portal</span>
          <div className="flex flex-wrap gap-2">
            {PRESETS_KB.map((kb) => (
              <button
                key={kb}
                onClick={() => {
                  setTargetKb(kb)
                  setCustom(false)
                }}
                className={cx(
                  'rounded-lg border px-3 py-1.5 text-sm font-semibold',
                  !custom && targetKb === kb ? 'border-brand-700 bg-brand-700 text-white' : 'border-slate-300 bg-white text-slate-700 hover:border-brand-500',
                )}
              >
                {targetLabel(kb)}
              </button>
            ))}
            <button
              onClick={() => setCustom(true)}
              className={cx('rounded-lg border px-3 py-1.5 text-sm font-semibold', custom ? 'border-brand-700 bg-brand-700 text-white' : 'border-slate-300 bg-white text-slate-700')}
            >
              Custom
            </button>
            {custom && (
              <span className="flex items-center gap-1.5">
                <Input type="number" min={20} max={100000} value={targetKb} onChange={(e) => setTargetKb(Number(e.target.value))} className="h-9 w-28" />
                <span className="text-sm text-slate-500">KB</span>
              </span>
            )}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Save as">
            <Select value={format} onChange={(e) => setFormat(e.target.value as 'pdf' | 'jpg')}>
              <option value="pdf">PDF</option>
              <option value="jpg">JPG image(s)</option>
            </Select>
          </Field>
          <Field label="Colour">
            <Select value={color} onChange={(e) => setColor(e.target.value)}>
              <option value="auto">Automatic (recommended)</option>
              <option value="color">Keep colour</option>
              <option value="gray">Grayscale</option>
              <option value="bw">Black & white (smallest)</option>
            </Select>
          </Field>
          <Field label="Student / reference (optional)">
            <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Sita Shrestha" />
          </Field>
        </div>

        <div className="flex flex-wrap gap-x-8 gap-y-3">
          {files.length > 1 && format === 'pdf' && (
            <Toggle checked={merge} onChange={setMerge} label="Combine into one PDF" hint="In the order shown above" />
          )}
          <Toggle checked={clean} onChange={setClean} label="Clean background" hint="White paper, no shadows or yellow tint" />
        </div>

        {showPassword ? (
          <Field label="PDF password" hint="Used once to open the file, then erased.">
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="max-w-xs" autoComplete="off" />
          </Field>
        ) : (
          <button onClick={() => setShowPassword(true)} className="flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline">
            <Lock className="size-3.5" /> PDF has a password? (bank statements)
          </button>
        )}

        {error && <Alert>{error}</Alert>}

        <div className="flex flex-wrap items-center gap-4">
          <Button size="lg" onClick={submit} disabled={!files.length} loading={progress !== null}>
            {progress !== null
              ? `Uploading ${Math.round(progress * 100)}%`
              : files.length > 1 && !(merge && format === 'pdf')
                ? `Compress ${files.length} files to ${targetLabel(targetKb)} each`
                : `Compress to under ${targetLabel(targetKb)}`}
          </Button>
          {progress !== null && (
            <div className="h-2 w-40 overflow-hidden rounded-full bg-slate-200">
              <div className="h-full bg-brand-600 transition-all" style={{ width: `${progress * 100}%` }} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
