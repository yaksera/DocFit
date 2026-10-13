import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { Logo } from '../components/Logo'
import { Alert, Button, Field, Input, Spinner, errorText } from '../components/ui'
import { api, ApiError, type Me } from '../lib/api'
import { useAuth } from '../lib/auth'

function Shell({ title, subtitle, children, footer }: { title: string; subtitle?: ReactNode; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-brand-50 to-slate-50 px-4 py-12">
      <Logo />
      <div className="card mt-8 w-full max-w-md p-8">
        <h1 className="text-xl font-bold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
        <div className="mt-6">{children}</div>
      </div>
      {footer && <p className="mt-6 text-sm text-slate-600">{footer}</p>}
    </div>
  )
}

function fieldError(e: unknown, field: string): string | undefined {
  if (e instanceof ApiError && e.errors) {
    const v = e.errors[field]
    if (Array.isArray(v)) return String(v[0])
    if (typeof v === 'string') return v
  }
}

export function Login() {
  const { me, setMe } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  if (me) return <Navigate to="/app" replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      setMe(await api<Me>('auth/login', { body: { email, password } }))
      nav('/app')
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Shell title="Log in" subtitle="Welcome back." footer={<>New to DocFit? <Link to="/register" className="font-semibold text-brand-700">Create an account</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert>{error}</Alert>}
        <Field label="Email">
          <Input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Password">
          <Input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <div className="-mt-1 text-right">
          <Link to="/forgot-password" className="text-sm font-medium text-brand-700 hover:underline">Forgot password?</Link>
        </div>
        <Button type="submit" loading={busy} className="w-full">Log in</Button>
      </form>
    </Shell>
  )
}

export function Register() {
  const { me, setMe } = useAuth()
  const nav = useNavigate()
  const [f, setF] = useState({ organization: '', full_name: '', email: '', phone: '', password: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  if (me) return <Navigate to="/app" replace />
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value })

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setMe(await api<Me>('auth/register', { body: f }))
      nav('/app')
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Shell
      title="Create your consultancy account"
      subtitle="Free plan: 25 documents a month. No card needed."
      footer={<>Already have an account? <Link to="/login" className="font-semibold text-brand-700">Log in</Link></>}
    >
      <form onSubmit={submit} className="space-y-4">
        {error != null && !(error instanceof ApiError && error.errors) && <Alert>{errorText(error)}</Alert>}
        <Field label="Consultancy name" error={fieldError(error, 'organization')}>
          <Input required value={f.organization} onChange={set('organization')} placeholder="e.g. Everest Education Consultancy" />
        </Field>
        <Field label="Your name" error={fieldError(error, 'full_name')}>
          <Input required value={f.full_name} onChange={set('full_name')} autoComplete="name" />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Email" error={fieldError(error, 'email')}>
            <Input type="email" required value={f.email} onChange={set('email')} autoComplete="email" />
          </Field>
          <Field label="Phone (optional)" error={fieldError(error, 'phone')}>
            <Input value={f.phone} onChange={set('phone')} placeholder="98XXXXXXXX" autoComplete="tel" />
          </Field>
        </div>
        <Field label="Password" hint="At least 8 characters, not too common." error={fieldError(error, 'password') ?? fieldError(error, 'non_field_errors')}>
          <Input type="password" required value={f.password} onChange={set('password')} autoComplete="new-password" />
        </Field>
        <Button type="submit" loading={busy} className="w-full">Create account</Button>
      </form>
    </Shell>
  )
}

export function AcceptInvite() {
  const { token = '' } = useParams()
  const { me, setMe } = useAuth()
  const nav = useNavigate()
  const [info, setInfo] = useState<{ organization: string; valid: boolean } | null>(null)
  const [loadError, setLoadError] = useState('')
  const [f, setF] = useState({ full_name: '', email: '', password: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    api<{ organization: string; valid: boolean }>(`invites/${token}`).then(setInfo, () => setLoadError('This invite link is not valid.'))
  }, [token])

  if (me) return <Navigate to="/app" replace />
  if (loadError) return <Shell title="Invite not found"><Alert>{loadError}</Alert></Shell>
  if (!info) return <Shell title="Loading invite…"><Spinner /></Shell>
  if (!info.valid)
    return (
      <Shell title="Invite expired">
        <Alert tone="amber">This invite link has expired or was already used. Ask {info.organization} for a new link.</Alert>
      </Shell>
    )
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value })

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setMe(await api<Me>(`invites/${token}`, { body: f }))
      nav('/app')
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Shell title={`Join ${info.organization}`} subtitle="Create your account to start compressing documents with your team.">
      <form onSubmit={submit} className="space-y-4">
        {error != null && !(error instanceof ApiError && error.errors) && <Alert>{errorText(error)}</Alert>}
        <Field label="Your name" error={fieldError(error, 'full_name')}>
          <Input required value={f.full_name} onChange={set('full_name')} />
        </Field>
        <Field label="Email" error={fieldError(error, 'email')}>
          <Input type="email" required value={f.email} onChange={set('email')} />
        </Field>
        <Field label="Password" error={fieldError(error, 'password') ?? fieldError(error, 'non_field_errors')}>
          <Input type="password" required value={f.password} onChange={set('password')} autoComplete="new-password" />
        </Field>
        <Button type="submit" loading={busy} className="w-full">Join team</Button>
      </form>
    </Shell>
  )
}

export function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api('auth/password-reset', { body: { email } })
      setSent(true)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Shell title="Reset your password" subtitle="We will email you a link to choose a new password." footer={<Link to="/login" className="font-semibold text-brand-700">Back to log in</Link>}>
      {sent ? (
        <Alert tone="green">If an account exists for {email}, a reset link is on its way. Check your inbox (and spam folder).</Alert>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Field label="Email">
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </Field>
          <Button type="submit" loading={busy} className="w-full">Send reset link</Button>
        </form>
      )}
    </Shell>
  )
}

export function ResetPassword() {
  const { uid = '', token = '' } = useParams()
  const [password, setPassword] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api('auth/password-reset/confirm', { body: { uid, token, password } })
      setDone(true)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }
  return (
    <Shell title="Choose a new password">
      {done ? (
        <div className="space-y-4">
          <Alert tone="green">Your password has been changed.</Alert>
          <Link to="/login" className="block rounded-lg bg-brand-700 py-2.5 text-center text-sm font-semibold text-white hover:bg-brand-800">Log in</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {error != null && <Alert>{fieldError(error, 'non_field_errors') ?? errorText(error)}</Alert>}
          <Field label="New password" hint="At least 8 characters, not too common.">
            <Input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
          </Field>
          <Button type="submit" loading={busy} className="w-full">Save password</Button>
        </form>
      )}
    </Shell>
  )
}
