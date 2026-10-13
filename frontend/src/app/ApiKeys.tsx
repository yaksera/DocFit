import { Copy, KeyRound, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Alert, Button, Input, PageHeader, errorText, useToast } from '../components/ui'
import { api } from '../lib/api'
import { useMe } from '../lib/auth'
import { ago } from '../lib/format'

interface Key {
  id: number
  name: string
  prefix: string
  created_at: string
  last_used_at: string | null
  key?: string
}

export default function ApiKeys() {
  const me = useMe()
  const toast = useToast()
  const [keys, setKeys] = useState<Key[]>([])
  const [name, setName] = useState('')
  const [fresh, setFresh] = useState<Key | null>(null)
  const [error, setError] = useState('')
  const load = useCallback(() => api<Key[]>('keys').then(setKeys).catch(() => {}), [])
  useEffect(() => {
    load()
  }, [load])

  async function create(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      setFresh(await api<Key>('keys', { body: { name } }))
      setName('')
      load()
    } catch (err) {
      setError(errorText(err))
    }
  }

  const origin = window.location.origin
  return (
    <>
      <PageHeader title="API keys" subtitle="Compress documents from your own CRM or student management system." />
      {!me.plan.api_access ? (
        <Alert tone="blue">
          API access is included in the Pro plan. <Link to="/app/billing" className="font-semibold underline">See plans</Link>
        </Alert>
      ) : (
        <>
          <form onSubmit={create} className="card mb-6 flex flex-wrap items-end gap-3 p-5">
            <label className="flex-1">
              <span className="mb-1.5 block text-sm font-medium text-slate-700">Key name</span>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Our CRM" required />
            </label>
            <Button type="submit"><KeyRound className="size-4" /> Create key</Button>
          </form>
          {error && <div className="mb-4"><Alert>{error}</Alert></div>}
          {fresh?.key && (
            <div className="mb-6">
              <Alert tone="green">
                <p className="font-semibold">Copy your key now. It will not be shown again.</p>
                <div className="mt-2 flex items-center gap-2">
                  <code className="min-w-0 flex-1 truncate rounded bg-white px-2 py-1 text-xs text-slate-800">{fresh.key}</code>
                  <Button size="sm" variant="secondary" onClick={() => navigator.clipboard.writeText(fresh.key!).then(() => toast('Key copied'))}>
                    <Copy className="size-3.5" /> Copy
                  </Button>
                </div>
              </Alert>
            </div>
          )}
          {keys.length > 0 && (
            <ul className="card mb-8 divide-y divide-slate-100">
              {keys.map((k) => (
                <li key={k.id} className="flex items-center gap-3 px-5 py-3 text-sm">
                  <span className="font-medium text-slate-900">{k.name}</span>
                  <code className="text-xs text-slate-500">{k.prefix}…</code>
                  <span className="ml-auto text-xs text-slate-500">{k.last_used_at ? `used ${ago(k.last_used_at)}` : 'never used'}</span>
                  <button className="rounded p-1.5 text-slate-400 hover:text-red-600" title="Revoke"
                    onClick={async () => {
                      if (!confirm(`Revoke "${k.name}"? Apps using it will stop working.`)) return
                      await api(`keys/${k.id}`, { method: 'DELETE' })
                      toast('Key revoked')
                      load()
                    }}>
                    <Trash2 className="size-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      <div className="card p-5">
        <h2 className="font-semibold text-slate-900">Quick start</h2>
        <p className="mt-1 text-sm text-slate-500">Upload, wait for <code>status: "done"</code>, then download.</p>
        <pre className="mt-4 overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs leading-relaxed text-slate-100">{`# 1. Upload (fields: target e.g. "4MB" or "500KB", color_mode, output_format, merge, label, password)
curl -H "Authorization: Bearer dfk_..." \\
     -F files=@transcript.pdf -F target=1MB -F label="Sita Shrestha" \\
     ${origin}/api/jobs

# 2. Check status (returns status, progress, output_bytes, met_target, warnings)
curl -H "Authorization: Bearer dfk_..." ${origin}/api/jobs/<id>

# 3. Download the result
curl -H "Authorization: Bearer dfk_..." -o small.pdf ${origin}/api/jobs/<id>/download`}</pre>
      </div>
    </>
  )
}
