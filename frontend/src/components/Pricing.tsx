import { Check } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { api, type Plan } from '../lib/api'
import { npr } from '../lib/format'
import { cx } from './ui'

export function usePlans() {
  const [plans, setPlans] = useState<Plan[]>([])
  useEffect(() => {
    api<Plan[]>('plans').then(setPlans).catch(() => setPlans([]))
  }, [])
  return plans
}

export function planFeatures(p: Plan): string[] {
  return [
    p.monthly_docs ? `${p.monthly_docs.toLocaleString()} documents / month` : 'Unlimited documents',
    `Up to ${p.max_upload_mb} MB and ${p.max_pages} pages per job`,
    p.seats === 1 ? '1 user' : `${p.seats} team members`,
    `Files auto-deleted after ${p.retention_hours < 24 ? `${p.retention_hours} hour${p.retention_hours > 1 ? 's' : ''}` : `${p.retention_hours / 24} day${p.retention_hours > 24 ? 's' : ''}`}`,
    ...(p.api_access ? ['API access for your CRM'] : []),
  ]
}

export function PlanCard({
  plan,
  highlight,
  current,
  action,
  yearly,
}: {
  plan: Plan
  highlight?: boolean
  current?: boolean
  action: ReactNode
  yearly?: boolean
}) {
  const price = yearly ? Math.round((plan.price_npr * 10) / 12) : plan.price_npr
  return (
    <div className={cx('card relative flex flex-col p-6', highlight && 'border-2 border-brand-700 shadow-lg')}>
      {highlight && (
        <span className="absolute -top-3 left-6 rounded-full bg-brand-700 px-3 py-0.5 text-xs font-semibold text-white">
          Most popular
        </span>
      )}
      <h3 className="text-lg font-semibold text-slate-900">{plan.name}</h3>
      <div className="mt-3 flex items-baseline gap-1">
        <span className="text-3xl font-extrabold tracking-tight text-slate-900">{plan.price_npr ? npr(price) : 'Free'}</span>
        {plan.price_npr > 0 && <span className="text-sm text-slate-500">/ month</span>}
      </div>
      {yearly && plan.price_npr > 0 && <p className="mt-1 text-xs text-green-700">Billed {npr(plan.price_npr * 10)} yearly (2 months free)</p>}
      <ul className="mt-5 mb-6 flex-1 space-y-2.5 text-sm text-slate-600">
        {planFeatures(plan).map((f) => (
          <li key={f} className="flex gap-2">
            <Check className="mt-0.5 size-4 shrink-0 text-green-600" />
            {f}
          </li>
        ))}
      </ul>
      {current ? <div className="rounded-lg bg-slate-100 py-2.5 text-center text-sm font-semibold text-slate-600">Current plan</div> : action}
    </div>
  )
}
