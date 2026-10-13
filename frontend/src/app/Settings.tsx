import { useState, type FormEvent } from 'react'
import { Alert, Button, Field, Input, PageHeader, Select, errorText, useToast } from '../components/ui'
import { api, type Me } from '../lib/api'
import { useAuth, useMe } from '../lib/auth'
import { targetLabel } from '../lib/format'
import { PRESETS_KB } from './Uploader'

export default function Settings() {
  const me = useMe()
  const { setMe } = useAuth()
  const toast = useToast()
  const manage = me.user.role !== 'member'
  const [name, setName] = useState(me.user.full_name)
  const [org, setOrg] = useState(me.organization)
  const [pw, setPw] = useState({ old_password: '', new_password: '' })
  const [pwError, setPwError] = useState('')
  const [orgError, setOrgError] = useState('')

  async function saveProfile(e: FormEvent) {
    e.preventDefault()
    try {
      setMe(await api<Me>('auth/me', { method: 'PATCH', body: { full_name: name } }))
      toast('Profile saved')
    } catch (err) {
      toast(errorText(err), 'red')
    }
  }

  async function saveOrg(e: FormEvent) {
    e.preventDefault()
    setOrgError('')
    try {
      setMe(await api<Me>('organization', { method: 'PATCH', body: { name: org.name, phone: org.phone, default_target_kb: org.default_target_kb } }))
      toast('Consultancy settings saved')
    } catch (err) {
      setOrgError(errorText(err))
    }
  }

  async function changePassword(e: FormEvent) {
    e.preventDefault()
    setPwError('')
    try {
      await api('auth/password', { body: pw })
      setPw({ old_password: '', new_password: '' })
      toast('Password changed')
    } catch (err) {
      setPwError(errorText(err))
    }
  }

  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid gap-6 lg:grid-cols-2">
        {manage && (
          <form onSubmit={saveOrg} className="card space-y-4 p-6">
            <h2 className="font-semibold text-slate-900">Consultancy</h2>
            {orgError && <Alert>{orgError}</Alert>}
            <Field label="Name"><Input value={org.name} onChange={(e) => setOrg({ ...org, name: e.target.value })} required /></Field>
            <Field label="Phone"><Input value={org.phone} onChange={(e) => setOrg({ ...org, phone: e.target.value })} /></Field>
            <Field label="Default size limit" hint="Pre-selected when your team uploads.">
              <Select value={org.default_target_kb} onChange={(e) => setOrg({ ...org, default_target_kb: Number(e.target.value) })}>
                {[...new Set([...PRESETS_KB, org.default_target_kb])].sort((a, b) => b - a).map((kb) => (
                  <option key={kb} value={kb}>{targetLabel(kb)}</option>
                ))}
              </Select>
            </Field>
            <Button type="submit">Save</Button>
          </form>
        )}
        <div className="space-y-6">
          <form onSubmit={saveProfile} className="card space-y-4 p-6">
            <h2 className="font-semibold text-slate-900">Your profile</h2>
            <Field label="Email"><Input value={me.user.email} disabled /></Field>
            <Field label="Name"><Input value={name} onChange={(e) => setName(e.target.value)} /></Field>
            <Button type="submit">Save</Button>
          </form>
          <form onSubmit={changePassword} className="card space-y-4 p-6">
            <h2 className="font-semibold text-slate-900">Change password</h2>
            {pwError && <Alert>{pwError}</Alert>}
            <Field label="Current password"><Input type="password" value={pw.old_password} onChange={(e) => setPw({ ...pw, old_password: e.target.value })} required autoComplete="current-password" /></Field>
            <Field label="New password"><Input type="password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} required autoComplete="new-password" /></Field>
            <Button type="submit">Change password</Button>
          </form>
        </div>
      </div>
    </>
  )
}
