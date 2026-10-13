import { Link } from 'react-router-dom'

export function LogoMark({ className = 'size-8' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="#1e40af" />
      <path d="M10 7h8l5 5v13a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z" fill="#fff" />
      <path d="M18 7v5h5" fill="#bfdbfe" />
      <path d="M12.5 19.5l3 3 5-6" stroke="#16a34a" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function Logo({ to = '/', light = false }: { to?: string; light?: boolean }) {
  return (
    <Link to={to} className="flex items-center gap-2">
      <LogoMark />
      <span className={`text-lg font-extrabold tracking-tight ${light ? 'text-white' : 'text-slate-900'}`}>
        Doc<span className={light ? 'text-brand-200' : 'text-brand-700'}>Fit</span>
      </span>
    </Link>
  )
}
