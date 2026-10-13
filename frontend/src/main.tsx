import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import ApiKeys from './app/ApiKeys'
import AppLayout from './app/AppLayout'
import Billing from './app/Billing'
import Dashboard from './app/Dashboard'
import JobDetail from './app/JobDetail'
import Settings from './app/Settings'
import Team from './app/Team'
import { ToastProvider } from './components/ui'
import './index.css'
import { AuthProvider } from './lib/auth'
import { AcceptInvite, ForgotPassword, Login, Register, ResetPassword } from './pages/Auth'
import Landing from './pages/Landing'

function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 text-center">
      <p className="text-5xl font-extrabold text-slate-300">404</p>
      <p className="text-slate-600">This page does not exist.</p>
      <Link to="/" className="font-semibold text-brand-700">Go home</Link>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/invite/:token" element={<AcceptInvite />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password/:uid/:token" element={<ResetPassword />} />
            <Route path="/app" element={<AppLayout />}>
              <Route index element={<Dashboard />} />
              <Route path="jobs/:id" element={<JobDetail />} />
              <Route path="team" element={<Team />} />
              <Route path="billing" element={<Billing />} />
              <Route path="api" element={<ApiKeys />} />
              <Route path="settings" element={<Settings />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
