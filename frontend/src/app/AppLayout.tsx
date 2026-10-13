import { CreditCard, FileText, KeyRound, LogOut, Menu, Settings, Users, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Logo } from '../components/Logo'
import { Spinner, cx } from '../components/ui'
import { useAuth } from '../lib/auth'

export default function AppLayout() {
  const { me, loading, logout } = useAuth()
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()
  useEffect(() => window.scrollTo(0, 0), [pathname])

  if (loading)
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    )
  if (!me) return <Navigate to="/login" replace />

  const manage = me.user.role !== 'member'
  const links = [
    { to: '/app', label: 'Documents', icon: FileText, end: true },
    { to: '/app/team', label: 'Team', icon: Users },
    ...(manage ? [{ to: '/app/billing', label: 'Plan & billing', icon: CreditCard }] : []),
    ...(manage ? [{ to: '/app/api', label: 'API keys', icon: KeyRound }] : []),
    { to: '/app/settings', label: 'Settings', icon: Settings },
  ]
  const { used, limit } = me.usage
  const pct = limit ? Math.min(100, (used / limit) * 100) : 0

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center justify-between px-5">
        <Logo to="/app" />
        <button className="rounded p-1 text-slate-500 lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu">
          <X className="size-5" />
        </button>
      </div>
      <div className="px-5 pb-4">
        <p className="truncate text-sm font-semibold text-slate-900">{me.organization.name}</p>
        <p className="text-xs text-slate-500">{me.plan.name} plan</p>
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {links.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={() => setOpen(false)}
            className={({ isActive }) =>
              cx(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium',
                isActive ? 'bg-brand-50 text-brand-800' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
              )
            }
          >
            <Icon className="size-4.5" /> {label}
          </NavLink>
        ))}
      </nav>
      <div className="m-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
        <p className="text-xs font-semibold text-slate-600">Documents this month</p>
        <p className="mt-1 text-sm font-bold text-slate-900">
          {used} {limit ? <span className="font-normal text-slate-500">of {limit.toLocaleString()}</span> : <span className="font-normal text-slate-500">(unlimited)</span>}
        </p>
        {limit > 0 && (
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
            <div className={cx('h-full rounded-full', pct > 90 ? 'bg-red-500' : 'bg-brand-600')} style={{ width: `${pct}%` }} />
          </div>
        )}
        {manage && me.plan.code === 'free' && (
          <NavLink to="/app/billing" className="mt-3 block text-xs font-semibold text-brand-700 hover:underline">
            Upgrade for more →
          </NavLink>
        )}
      </div>
      <div className="flex items-center justify-between border-t border-slate-200 px-5 py-4">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-slate-900">{me.user.full_name || me.user.email}</p>
          <p className="truncate text-xs text-slate-500">{me.user.email}</p>
        </div>
        <button
          onClick={async () => {
            await logout()
            nav('/')
          }}
          className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
          title="Log out"
          aria-label="Log out"
        >
          <LogOut className="size-4.5" />
        </button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-slate-200 bg-white lg:block">{sidebar}</aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 bg-white shadow-xl">{sidebar}</aside>
        </div>
      )}
      <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-slate-200 bg-white px-4 lg:hidden">
        <button onClick={() => setOpen(true)} className="rounded p-1.5 text-slate-600 hover:bg-slate-100" aria-label="Open menu">
          <Menu className="size-5" />
        </button>
        <Logo to="/app" />
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
