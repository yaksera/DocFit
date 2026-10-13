import { FileArchive, Files, Search } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Button, Input, PageHeader, Select, Spinner, errorText, useToast } from '../components/ui'
import { api, ensureCsrf, type Job, type Page } from '../lib/api'
import { useAuth } from '../lib/auth'
import { bytes } from '../lib/format'
import JobRow from './JobRow'
import Uploader from './Uploader'

interface Stats {
  total_docs: number
  bytes_saved: number
  docs_this_month: number
  fit_rate: number | null
}

export default function Dashboard() {
  const { refresh } = useAuth()
  const toast = useToast()
  const [jobs, setJobs] = useState<Job[]>([])
  const [count, setCount] = useState(0)
  const [pageNo, setPageNo] = useState(1)
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [stats, setStats] = useState<Stats | null>(null)
  const [zipping, setZipping] = useState(false)
  const jobsRef = useRef(jobs)
  jobsRef.current = jobs

  const load = useCallback(async () => {
    const params = new URLSearchParams({ page: String(pageNo) })
    if (q) params.set('q', q)
    if (status) params.set('status', status)
    try {
      const data = await api<Page<Job>>(`jobs?${params}`)
      setJobs(data.results)
      setCount(data.count)
    } catch (e) {
      toast(errorText(e), 'red')
    } finally {
      setLoading(false)
    }
  }, [pageNo, q, status, toast])

  const loadStats = useCallback(() => api<Stats>('jobs/stats').then(setStats).catch(() => {}), [])

  useEffect(() => {
    const t = setTimeout(load, q ? 300 : 0)
    return () => clearTimeout(t)
  }, [load, q])
  useEffect(() => {
    loadStats()
  }, [loadStats])

  // Poll only the jobs that are still running.
  useEffect(() => {
    const timer = setInterval(async () => {
      const active = jobsRef.current.filter((j) => j.status === 'queued' || j.status === 'processing')
      if (!active.length) return
      try {
        const data = await api<Page<Job>>(`jobs?ids=${active.map((j) => j.id).join(',')}`)
        const byId = new Map(data.results.map((j) => [j.id, j]))
        if (data.results.some((j) => j.status === 'done' || j.status === 'failed')) {
          loadStats()
          refresh()
        }
        setJobs((cur) => cur.map((j) => byId.get(j.id) ?? j))
      } catch {
        /* transient network issue: try again next tick */
      }
    }, 1500)
    return () => clearInterval(timer)
  }, [loadStats, refresh])

  const upsert = (j: Job) => setJobs((cur) => cur.map((x) => (x.id === j.id ? j : x)))

  async function downloadZip() {
    setZipping(true)
    try {
      await ensureCsrf()
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? ''
      const res = await fetch('/api/jobs/zip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ ids: [...selected] }),
      })
      if (!res.ok) throw new Error('Could not build the ZIP. Some files may have expired.')
      const url = URL.createObjectURL(await res.blob())
      const a = Object.assign(document.createElement('a'), { href: url, download: 'docfit-files.zip' })
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      toast(errorText(e), 'red')
    } finally {
      setZipping(false)
    }
  }

  const pages = Math.ceil(count / 25)

  return (
    <>
      <PageHeader title="Documents" subtitle="Upload, compress to the portal’s limit, download." />

      {stats && stats.total_docs > 0 && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ['This month', stats.docs_this_month.toLocaleString()],
            ['All time', stats.total_docs.toLocaleString()],
            ['Space saved', bytes(stats.bytes_saved)],
            ['Fit the limit', stats.fit_rate != null ? `${stats.fit_rate}%` : '–'],
          ].map(([k, v]) => (
            <div key={k} className="card px-4 py-3">
              <p className="text-xs font-medium text-slate-500">{k}</p>
              <p className="mt-0.5 text-xl font-bold text-slate-900">{v}</p>
            </div>
          ))}
        </div>
      )}

      <Uploader
        onCreated={(created) => {
          setPageNo(1)
          setJobs((cur) => [...created, ...cur.filter((j) => !created.some((c) => c.id === j.id))])
          setCount((c) => c + created.length)
        }}
      />

      <div className="card mt-8">
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 px-4 py-3 sm:px-5">
          <h2 className="mr-auto font-semibold text-slate-900">Recent documents</h2>
          {selected.size > 0 && (
            <Button size="sm" variant="secondary" onClick={downloadZip} loading={zipping}>
              <FileArchive className="size-4" /> Download {selected.size} as ZIP
            </Button>
          )}
          <div className="relative">
            <Search className="pointer-events-none absolute top-2.5 left-2.5 size-4 text-slate-400" />
            <Input placeholder="Search file or student" value={q} onChange={(e) => { setQ(e.target.value); setPageNo(1) }} className="h-9 w-52 pl-8" />
          </div>
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setPageNo(1) }} className="h-9 w-36">
            <option value="">All</option>
            <option value="done">Ready</option>
            <option value="processing">Processing</option>
            <option value="failed">Failed</option>
            <option value="expired">Deleted</option>
          </Select>
        </div>

        {loading ? (
          <div className="flex justify-center py-16"><Spinner /></div>
        ) : jobs.length === 0 ? (
          <div className="flex flex-col items-center py-16 text-center">
            <Files className="size-10 text-slate-300" />
            <p className="mt-3 font-medium text-slate-700">{q || status ? 'No documents match.' : 'No documents yet'}</p>
            <p className="text-sm text-slate-500">{q || status ? 'Try another search.' : 'Upload your first file above.'}</p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {jobs.map((j) => (
              <JobRow
                key={j.id}
                job={j}
                selected={selected.has(j.id)}
                onSelect={(v) =>
                  setSelected((s) => {
                    const n = new Set(s)
                    if (v) n.add(j.id)
                    else n.delete(j.id)
                    return n
                  })
                }
                onChange={upsert}
                onDelete={(id) => {
                  setJobs((cur) => cur.filter((x) => x.id !== id))
                  setCount((c) => c - 1)
                  loadStats()
                }}
              />
            ))}
          </ul>
        )}
        {pages > 1 && (
          <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3 text-sm">
            <span className="text-slate-500">Page {pageNo} of {pages}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={pageNo <= 1} onClick={() => setPageNo(pageNo - 1)}>Previous</Button>
              <Button size="sm" variant="secondary" disabled={pageNo >= pages} onClick={() => setPageNo(pageNo + 1)}>Next</Button>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
