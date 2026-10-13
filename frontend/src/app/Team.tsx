import { Copy, Link2, Trash2, UserMinus } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Alert, Badge, Button, PageHeader, Select, Spinner, errorText, useToast } from '../components/ui'
import { api, type User } from '../lib/api'
import { useMe } from '../lib/auth'
import { ago, until } from '../lib/format'

interface Invite {
  id: number
  role: string
  url: string
  created_at: string
  expires_at: string
}

export default function Team() {
  const me = useMe()
  const toast = useToast()
  const manage = me.user.role !== 'member'
  const [data, setData] = useState<{ members: User[]; seats: number; invites?: Invite[] } | null>(null)
  const [role, setRole] = useState('member')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => api<typeof data>('team').then(setData).catch((e) => setError(errorText(e))), [])
  useEffect(() => {
    load()
  }, [load])

  async function invite() {
    setBusy(true)
    setError('')
    try {
      const inv = await api<Invite>('team/invites', { body: { role } })
      await navigator.clipboard?.writeText(inv.url).catch(() => {})
      toast('Invite link created and copied')
      load()
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  async function act(fn: () => Promise<unknown>, msg: string) {
    try {
      await fn()
      toast(msg)
      load()
    } catch (e) {
      toast(errorText(e), 'red')
    }
  }

  if (!data) return error ? <Alert>{error}</Alert> : <div className="flex justify-center py-20"><Spinner /></div>
  const used = data.members.length + (data.invites?.length ?? 0)

  return (
    <>
      <PageHeader title="Team" subtitle={`${data.members.length} member${data.members.length > 1 ? 's' : ''} · ${data.seats} seat${data.seats > 1 ? 's' : ''} on your ${me.plan.name} plan`} />
      {manage && (
        <div className="card mb-6 p-5">
          <h2 className="font-semibold text-slate-900">Invite a counsellor</h2>
          <p className="mt-1 text-sm text-slate-500">Create a link and send it on WhatsApp, Viber or email. It works once and expires in 7 days.</p>
          {error && <div className="mt-3"><Alert>{error}</Alert></div>}
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Select value={role} onChange={(e) => setRole(e.target.value)} className="w-56">
              <option value="member">Member: compress documents</option>
              <option value="admin">Admin: also manage team & billing</option>
            </Select>
            <Button onClick={invite} loading={busy} disabled={used >= data.seats}>
              <Link2 className="size-4" /> Create invite link
            </Button>
            {used >= data.seats && <span className="text-sm text-amber-700">All seats are in use. Upgrade to add more people.</span>}
          </div>
          {data.invites && data.invites.length > 0 && (
            <ul className="mt-5 divide-y divide-slate-100 rounded-lg border border-slate-200">
              {data.invites.map((i) => (
                <li key={i.id} className="flex flex-wrap items-center gap-3 px-3 py-2.5 text-sm">
                  <Badge tone="blue">{i.role}</Badge>
                  <code className="min-w-0 flex-1 truncate text-xs text-slate-600">{i.url}</code>
                  <span className="text-xs text-slate-500">expires {until(i.expires_at)}</span>
                  <Button size="sm" variant="secondary" onClick={() => navigator.clipboard.writeText(i.url).then(() => toast('Link copied'))}>
                    <Copy className="size-3.5" /> Copy
                  </Button>
                  <button className="rounded p-1.5 text-slate-400 hover:text-red-600" title="Cancel invite"
                    onClick={() => act(() => api(`team/invites/${i.id}`, { method: 'DELETE' }), 'Invite cancelled')}>
                    <Trash2 className="size-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
            <tr>
              <th className="px-5 py-3">Name</th>
              <th className="px-5 py-3">Role</th>
              <th className="hidden px-5 py-3 sm:table-cell">Last active</th>
              {manage && <th className="px-5 py-3" />}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.members.map((m) => (
              <tr key={m.id}>
                <td className="px-5 py-3">
                  <p className="font-medium text-slate-900">{m.full_name || '—'} {m.id === me.user.id && <span className="text-slate-400">(you)</span>}</p>
                  <p className="text-xs text-slate-500">{m.email}</p>
                </td>
                <td className="px-5 py-3">
                  {manage && m.role !== 'owner' && m.id !== me.user.id ? (
                    <Select value={m.role} className="h-8 w-28"
                      onChange={(e) => act(() => api(`team/members/${m.id}`, { method: 'PATCH', body: { role: e.target.value } }), 'Role updated')}>
                      <option value="member">Member</option>
                      <option value="admin">Admin</option>
                    </Select>
                  ) : (
                    <Badge tone={m.role === 'owner' ? 'blue' : 'slate'}>{m.role}</Badge>
                  )}
                </td>
                <td className="hidden px-5 py-3 text-slate-500 sm:table-cell">{m.last_login ? ago(m.last_login) : 'never'}</td>
                {manage && (
                  <td className="px-5 py-3 text-right">
                    {m.role !== 'owner' && m.id !== me.user.id && (
                      <button className="rounded p-1.5 text-slate-400 hover:text-red-600" title="Remove from team"
                        onClick={() => confirm(`Remove ${m.email} from the team?`) && act(() => api(`team/members/${m.id}`, { method: 'DELETE' }), 'Member removed')}>
                        <UserMinus className="size-4" />
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
