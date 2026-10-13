import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PlanCard, usePlans } from '../components/Pricing'
import { Alert, Badge, Button, PageHeader, cx, errorText } from '../components/ui'
import { api } from '../lib/api'
import { useAuth, useMe } from '../lib/auth'
import { date, npr } from '../lib/format'

interface Payment {
  id: number
  plan: string
  months: number
  amount_npr: number
  status: string
  transaction_id: string
  created_at: string
}

export default function Billing() {
  const me = useMe()
  const { refresh } = useAuth()
  const plans = usePlans()
  const [params, setParams] = useSearchParams()
  const [yearly, setYearly] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [payments, setPayments] = useState<Payment[]>([])
  const result = params.get('payment')

  useEffect(() => {
    api<Payment[]>('billing/payments').then(setPayments).catch(() => {})
    if (result === 'success') refresh()
  }, [result, refresh])

  async function pay(code: string) {
    setBusy(code)
    setError('')
    try {
      const { payment_url } = await api<{ payment_url: string }>('billing/khalti/initiate', { body: { plan: code, months: yearly ? 12 : 1 } })
      window.location.href = payment_url
    } catch (e) {
      setError(errorText(e))
      setBusy('')
    }
  }

  return (
    <>
      <PageHeader
        title="Plan & billing"
        subtitle={
          <>
            You are on the <b>{me.plan.name}</b> plan
            {me.plan_expires_at && <> until <b>{date(me.plan_expires_at)}</b></>}.
          </>
        }
      />
      {result && (
        <div className="mb-6">
          {result === 'success' && <Alert tone="green">Payment received. Your plan is active. Thank you!</Alert>}
          {result === 'pending' && <Alert tone="amber">Your payment is still being confirmed by Khalti. Refresh this page in a minute.</Alert>}
          {result === 'failed' && <Alert>The payment was not completed. You have not been charged. Please try again.</Alert>}
          <button className="mt-2 text-xs text-slate-500 underline" onClick={() => setParams({})}>Dismiss</button>
        </div>
      )}
      {!me.payments_enabled && (
        <div className="mb-6">
          <Alert tone="blue">Online payment is not switched on yet. To upgrade, contact us and we will activate your plan.</Alert>
        </div>
      )}
      {error && <div className="mb-6"><Alert>{error}</Alert></div>}

      <div className="mb-6 inline-flex rounded-lg border border-slate-300 bg-white p-1 text-sm font-semibold">
        {[false, true].map((y) => (
          <button key={String(y)} onClick={() => setYearly(y)} className={cx('rounded-md px-4 py-1.5', yearly === y ? 'bg-brand-700 text-white' : 'text-slate-600')}>
            {y ? 'Yearly (2 months free)' : 'Monthly'}
          </button>
        ))}
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        {plans.map((p) => (
          <PlanCard
            key={p.code}
            plan={p}
            yearly={yearly}
            highlight={p.code === 'starter' && me.plan.code === 'free'}
            current={p.code === me.plan.code}
            action={
              p.price_npr > 0 ? (
                <Button onClick={() => pay(p.code)} loading={busy === p.code} disabled={!me.payments_enabled || !!busy} className="w-full bg-[#5c2d91] hover:bg-[#4a2475]">
                  Pay {npr(yearly ? p.price_npr * 10 : p.price_npr)} with Khalti
                </Button>
              ) : (
                <div className="py-2.5 text-center text-sm text-slate-500">Always free</div>
              )
            }
          />
        ))}
      </div>
      {me.plan.price_npr > 0 && (
        <p className="mt-4 text-sm text-slate-500">Paying again for your current plan adds the time to your remaining period.</p>
      )}

      {payments.length > 0 && (
        <div className="card mt-10 overflow-hidden">
          <h2 className="border-b border-slate-200 px-5 py-3 font-semibold text-slate-900">Payment history</h2>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-slate-100">
              {payments.map((p) => (
                <tr key={p.id}>
                  <td className="px-5 py-3 text-slate-600">{date(p.created_at)}</td>
                  <td className="px-5 py-3 font-medium text-slate-900">{p.plan} · {p.months === 12 ? '1 year' : '1 month'}</td>
                  <td className="px-5 py-3">{npr(p.amount_npr)}</td>
                  <td className="px-5 py-3">
                    <Badge tone={p.status === 'completed' ? 'green' : p.status === 'failed' ? 'red' : 'amber'}>{p.status}</Badge>
                  </td>
                  <td className="hidden px-5 py-3 text-xs text-slate-500 sm:table-cell">{p.transaction_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
