import {
  ArrowRight,
  Building2,
  CircleCheckBig,
  Files,
  Lock,
  Plug,
  ScanLine,
  ShieldCheck,
  Target,
  Type,
  Users,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { Logo } from '../components/Logo'
import { PlanCard, usePlans } from '../components/Pricing'
import { useAuth } from '../lib/auth'

const features = [
  { icon: Target, title: 'Hits the exact limit', text: 'Choose 4 MB, 1 MB, 500 KB or any size. DocFit finds the best quality that still fits, so you never get "file too large" again.' },
  { icon: Type, title: 'Text stays sharp', text: 'Text, stamps and signatures are kept as crisp shapes, apart from the paper. Small print stays readable even at tiny sizes.' },
  { icon: ScanLine, title: 'Phone photos become clean scans', text: 'Students send WhatsApp photos? DocFit crops the table, removes shadows and whitens the paper automatically.' },
  { icon: Files, title: 'Merge into one PDF', text: 'Combine marksheets, character certificate and passport into a single PDF under the limit, in your chosen order.' },
  { icon: Lock, title: 'Bank statements with passwords', text: 'Open password-protected statements, compress them, and get a normal PDF the portal accepts.' },
  { icon: ShieldCheck, title: 'Private by design', text: 'Files are deleted automatically after a few hours. Each consultancy only sees its own documents.' },
  { icon: Users, title: 'Built for teams', text: 'Invite counsellors with a link, tag files by student name, and download a whole batch as one ZIP.' },
  { icon: Plug, title: 'API for your CRM', text: 'Compress documents straight from your own student management system with a simple REST API.' },
]

const faqs = [
  ['Is the quality really better than free tools?', 'Free tools shrink everything as one blurry photo. DocFit separates the text from the background and compresses each the right way, the method professional scanners use. Text stays sharp at sizes where other tools turn it into mush.'],
  ['Which portals does it work for?', 'Any portal with an upload size limit: university applications, VFS and embassy visa portals, UCAS, Common App, IELTS/PTE registrations, scholarship forms and more. The output is a standard PDF or JPG.'],
  ['What if the document cannot reach my size?', 'DocFit tells you clearly instead of handing you an unreadable file. You can then try black & white mode, or split the document.'],
  ['Are my students’ documents safe?', 'Files are stored privately, never shared, and deleted automatically after the retention time of your plan (1 hour on Free). Passwords for protected PDFs are erased right after use.'],
  ['How do I pay?', 'Pay monthly or yearly with Khalti. Need an invoice or bank transfer for a bigger team? Contact us.'],
]

export default function Landing() {
  const plans = usePlans()
  const { me } = useAuth()
  const cta = me ? '/app' : '/register'

  return (
    <div className="bg-white">
      <header className="sticky top-0 z-40 border-b border-slate-200/70 bg-white/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <Logo />
          <nav className="hidden items-center gap-7 text-sm font-medium text-slate-600 md:flex">
            <a href="#how" className="hover:text-slate-900">How it works</a>
            <a href="#features" className="hover:text-slate-900">Features</a>
            <a href="#pricing" className="hover:text-slate-900">Pricing</a>
            <a href="#faq" className="hover:text-slate-900">FAQ</a>
          </nav>
          <div className="flex items-center gap-2">
            {me ? (
              <Link to="/app" className="rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800">Open dashboard</Link>
            ) : (
              <>
                <Link to="/login" className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100">Log in</Link>
                <Link to="/register" className="rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800">Start free</Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-b from-brand-50 to-white">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 md:py-24 lg:grid-cols-2">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-white px-3 py-1 text-xs font-semibold text-brand-800">
              <Building2 className="size-3.5" /> Made for education consultancies in Nepal
            </span>
            <h1 className="mt-5 text-4xl font-extrabold tracking-tight text-slate-900 sm:text-5xl">
              Every document under the upload limit. <span className="text-brand-700">Text still sharp.</span>
            </h1>
            <p className="mt-5 max-w-xl text-lg text-slate-600">
              Transcripts, passports, bank statements and phone photos, shrunk to 4 MB, 1 MB or 500 KB in seconds, without the blurry
              mess free compressors produce.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to={cta} className="inline-flex items-center gap-2 rounded-lg bg-brand-700 px-6 py-3 font-semibold text-white shadow-sm hover:bg-brand-800">
                Compress your first document <ArrowRight className="size-4" />
              </Link>
              <a href="#pricing" className="rounded-lg border border-slate-300 bg-white px-6 py-3 font-semibold text-slate-700 hover:bg-slate-50">See pricing</a>
            </div>
            <p className="mt-4 text-sm text-slate-500">Free plan: 25 documents a month, no card needed.</p>
          </div>

          <div className="card relative mx-auto w-full max-w-md p-6 shadow-xl">
            <p className="text-xs font-semibold tracking-wide text-slate-500 uppercase">Example result</p>
            <div className="mt-3 flex items-center gap-3">
              <div className="flex size-11 items-center justify-center rounded-lg bg-red-50 text-xs font-bold text-red-600">PDF</div>
              <div className="min-w-0">
                <p className="truncate font-semibold text-slate-900">transcript_scan.pdf</p>
                <p className="text-sm text-slate-500">4 pages, colour scan at 300 dpi</p>
              </div>
            </div>
            <div className="mt-6 grid grid-cols-[1fr_auto_1fr] items-center gap-3 text-center">
              <div className="rounded-xl bg-slate-100 py-4">
                <p className="text-2xl font-extrabold text-slate-400 line-through decoration-2">104 MB</p>
                <p className="text-xs text-slate-500">Original</p>
              </div>
              <ArrowRight className="size-5 text-slate-400" />
              <div className="rounded-xl bg-green-50 py-4 ring-1 ring-green-200">
                <p className="text-2xl font-extrabold text-green-700">528 KB</p>
                <p className="text-xs text-green-700">197× smaller</p>
              </div>
            </div>
            <ul className="mt-6 space-y-2 text-sm">
              {['Fits the 700 KB limit', 'Text quality: excellent', 'Stamp and signature colours kept', 'Passport photo kept as a photo'].map((t) => (
                <li key={t} className="flex items-center gap-2 text-slate-700">
                  <CircleCheckBig className="size-4 text-green-600" /> {t}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* How */}
      <section id="how" className="mx-auto max-w-6xl px-4 py-20">
        <h2 className="text-center text-3xl font-bold tracking-tight text-slate-900">Why DocFit files look better</h2>
        <p className="mx-auto mt-3 max-w-2xl text-center text-slate-600">
          Free compressors squeeze the whole page as one photo, so the text is the first thing to blur. DocFit takes the page apart
          first.
        </p>
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {[
            ['1', 'Separate', 'Text, stamps, signatures, photos and the paper are detected and split into layers.'],
            ['2', 'Compress each the right way', 'Text becomes razor-sharp shapes, the paper is cleaned and shrunk, and photos keep their tones.'],
            ['3', 'Fit the limit', 'DocFit tries quality levels until the file lands just under your limit, then checks the result.'],
          ].map(([n, t, d]) => (
            <div key={n} className="card p-6">
              <span className="flex size-9 items-center justify-center rounded-full bg-brand-700 font-bold text-white">{n}</span>
              <h3 className="mt-4 font-semibold text-slate-900">{t}</h3>
              <p className="mt-2 text-sm text-slate-600">{d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="bg-slate-50 py-20">
        <div className="mx-auto max-w-6xl px-4">
          <h2 className="text-center text-3xl font-bold tracking-tight text-slate-900">Everything a consultancy needs</h2>
          <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {features.map(({ icon: Icon, title, text }) => (
              <div key={title} className="card p-5">
                <Icon className="size-6 text-brand-700" />
                <h3 className="mt-3 font-semibold text-slate-900">{title}</h3>
                <p className="mt-1.5 text-sm text-slate-600">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="mx-auto max-w-6xl px-4 py-20">
        <h2 className="text-center text-3xl font-bold tracking-tight text-slate-900">Simple pricing in rupees</h2>
        <p className="mt-3 text-center text-slate-600">Start free. Upgrade when your team needs more.</p>
        <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {plans.map((p) => (
            <PlanCard
              key={p.code}
              plan={p}
              highlight={p.code === 'starter'}
              action={
                <Link to={cta} className="block rounded-lg bg-brand-700 py-2.5 text-center text-sm font-semibold text-white hover:bg-brand-800">
                  {p.price_npr ? `Get ${p.name}` : 'Start free'}
                </Link>
              }
            />
          ))}
          <div className="card flex flex-col bg-slate-900 p-6 text-white">
            <h3 className="text-lg font-semibold">Business</h3>
            <p className="mt-3 text-3xl font-extrabold tracking-tight">Custom</p>
            <ul className="mt-5 mb-6 flex-1 space-y-2.5 text-sm text-slate-300">
              {['Unlimited documents', '50+ team members', 'Branches and franchises', 'Invoice / bank transfer', 'Priority support'].map((f) => (
                <li key={f} className="flex gap-2">
                  <CircleCheckBig className="mt-0.5 size-4 shrink-0 text-green-400" /> {f}
                </li>
              ))}
            </ul>
            <a href="mailto:sales@docfit.app" className="block rounded-lg bg-white py-2.5 text-center text-sm font-semibold text-slate-900 hover:bg-slate-100">
              Contact sales
            </a>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="bg-slate-50 py-20">
        <div className="mx-auto max-w-3xl px-4">
          <h2 className="text-center text-3xl font-bold tracking-tight text-slate-900">Questions</h2>
          <div className="mt-10 space-y-3">
            {faqs.map(([q, a]) => (
              <details key={q} className="card group p-5">
                <summary className="cursor-pointer list-none font-semibold text-slate-900 marker:hidden">
                  <span className="flex items-center justify-between gap-4">
                    {q}
                    <span className="text-slate-400 transition-transform group-open:rotate-45">+</span>
                  </span>
                </summary>
                <p className="mt-3 text-sm text-slate-600">{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-brand-900">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-6 px-4 py-16 text-center">
          <h2 className="text-3xl font-bold tracking-tight text-white">Stop fighting upload limits.</h2>
          <Link to={cta} className="inline-flex items-center gap-2 rounded-lg bg-white px-6 py-3 font-semibold text-brand-900 hover:bg-brand-50">
            Start free <ArrowRight className="size-4" />
          </Link>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm text-slate-500">
          <Logo />
          <p>© {new Date().getFullYear()} DocFit · Made in Nepal</p>
        </div>
      </footer>
    </div>
  )
}
