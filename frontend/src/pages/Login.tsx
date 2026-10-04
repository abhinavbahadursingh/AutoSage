import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, LogIn, User, Shield, Zap } from 'lucide-react'
import { api, ensureToken, setCachedUser } from '../lib/api'
import { loginAsGuest } from '../lib/guestAuth'
import { useStore } from '../store/store'
import { Logo } from '../components/layout/Sidebar'
import { ThemeToggle } from '../components/ui/ThemeToggle'

export function LoginPage() {
  const navigate = useNavigate()
  const { setAuthError, setUser, toast } = useStore()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleGuestLogin = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const guest = await loginAsGuest()
      setUser(guest)
      setAuthError(null)
      toast({ title: 'Welcome, Guest!', detail: 'You have full access to all features.', tone: 'success' })
      navigate('/workspace', { replace: true })
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Guest login failed'
      setError(msg)
      setAuthError(msg)
      toast({ title: 'Guest login failed', detail: msg, tone: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  const handleDevLogin = async () => {
    setIsLoading(true)
    setError(null)
    try {
      await ensureToken(true)
      const user = await api.me()
      setCachedUser(user)
      setAuthError(null)
      toast({ title: 'Signed in', detail: `Welcome back, ${user.name ?? user.email}`, tone: 'success' })
      navigate('/workspace', { replace: true })
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Login failed'
      setError(msg)
      setAuthError(msg)
      toast({ title: 'Login failed', detail: msg, tone: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center p-4"
      style={{ color: 'var(--as-text)' }}
    >
      {/* Theme toggle in top-right */}
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>

      <div className="w-full max-w-sm">
        {/* Logo + title */}
        <div className="text-center mb-10">
          <div className="flex justify-center mb-5">
            <Logo />
          </div>
          <h1
            className="text-[26px] font-semibold tracking-tight"
            style={{ color: 'var(--as-text)' }}
          >
            Welcome back
          </h1>
          <p className="mt-1.5 text-[15px]" style={{ color: 'var(--as-text-3)' }}>
            Sign in to access your workspace
          </p>
        </div>

        {/* Glass card */}
        <div
          className="glass grain rounded-3xl p-7 space-y-3"
          style={{ boxShadow: 'var(--as-glass-shadow), 0 0 60px var(--as-accent-glow)' }}
        >
          {/* Continue as Guest */}
          <button
            onClick={handleGuestLogin}
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-3 px-4 py-3.5 rounded-2xl border font-medium text-[15px] transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:-translate-y-0.5 active:translate-y-0"
            style={{
              background: 'color-mix(in oklch, var(--as-verify) 10%, transparent)',
              borderColor: 'color-mix(in oklch, var(--as-verify) 30%, transparent)',
              color: 'var(--as-verify)',
            }}
          >
            {isLoading ? (
              <><Loader2 className="w-4 h-4 animate-spin" /><span>Creating guest session…</span></>
            ) : (
              <><Zap className="w-4 h-4" /><span>Continue as Guest</span></>
            )}
          </button>

          {/* Divider */}
          <div className="relative py-1">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full" style={{ borderTop: '1px solid var(--as-border)' }} />
            </div>
            <div className="relative flex justify-center text-[12.5px]">
              <span
                className="px-3"
                style={{ background: 'var(--as-glass-bg)', color: 'var(--as-text-3)' }}
              >
                or
              </span>
            </div>
          </div>

          {/* Dev Token login */}
          <button
            onClick={handleDevLogin}
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-3 px-4 py-3.5 rounded-2xl border font-medium text-[15px] transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:-translate-y-0.5 active:translate-y-0"
            style={{
              background: 'color-mix(in oklch, var(--as-accent) 10%, transparent)',
              borderColor: 'color-mix(in oklch, var(--as-accent) 30%, transparent)',
              color: 'var(--as-accent-hi)',
            }}
          >
            {isLoading ? (
              <><Loader2 className="w-4 h-4 animate-spin" /><span>Signing in…</span></>
            ) : (
              <><LogIn className="w-4 h-4" /><span>Sign in with Dev Token</span></>
            )}
          </button>

          {/* Error state */}
          {error && (
            <div
              className="rounded-2xl border p-3.5 text-[13.5px]"
              style={{
                background: 'color-mix(in oklch, var(--as-error) 8%, transparent)',
                borderColor: 'color-mix(in oklch, var(--as-error) 30%, transparent)',
                color: 'var(--as-error)',
              }}
            >
              {error}
            </div>
          )}
        </div>

        {/* Info badges */}
        <div className="mt-7 space-y-2">
          {[
            { icon: Shield, text: 'Guest sessions last 7 days' },
            { icon: User, text: 'Full access to all features' },
            { icon: Zap, text: 'No account required' },
          ].map(({ icon: Icon, text }) => (
            <div
              key={text}
              className="flex items-center justify-center gap-2 text-[13px]"
              style={{ color: 'var(--as-text-3)' }}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{text}</span>
            </div>
          ))}
        </div>

        <p className="mt-6 text-center text-[12px]" style={{ color: 'var(--as-text-3)' }}>
          By continuing, you agree to our{' '}
          <a
            href="#"
            className="underline underline-offset-2 transition-colors"
            style={{ color: 'var(--as-text-2)' }}
          >
            Terms
          </a>{' '}
          and{' '}
          <a
            href="#"
            className="underline underline-offset-2 transition-colors"
            style={{ color: 'var(--as-text-2)' }}
          >
            Privacy Policy
          </a>
        </p>
      </div>
    </div>
  )
}
