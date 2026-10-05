import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, LogIn, User, Shield, Zap, KeyRound } from 'lucide-react'
import { api, ensureToken, isDevTokenAllowed, loginWithToken, setCachedUser } from '../lib/api'
import { isSupabaseConfigured, supabaseSignIn, supabaseSignUp } from '../lib/supabaseAuth'
import { loginAsGuest } from '../lib/guestAuth'
import { useStore } from '../store/store'
import { Logo } from '../components/layout/Sidebar'
import { ThemeToggle } from '../components/ui/ThemeToggle'

const inputStyle: React.CSSProperties = {
  width: '100%',
  borderRadius: '14px',
  border: '1px solid var(--as-border)',
  background: 'color-mix(in oklch, var(--as-bg) 60%, transparent)',
  color: 'var(--as-text)',
  padding: '10px 14px',
  fontSize: '14.5px',
  outline: 'none',
}

export function LoginPage() {
  const navigate = useNavigate()
  const { setAuthError, setUser, toast } = useStore()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const devAllowed = isDevTokenAllowed()
  const supabaseReady = isSupabaseConfigured()

  // Production Supabase form state
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')

  // Paste-an-access-token fallback (works with any backend-accepted JWT)
  const [showTokenForm, setShowTokenForm] = useState(false)
  const [pastedToken, setPastedToken] = useState('')

  const finishLogin = (user: { name?: string | null; email: string }, title: string) => {
    setUser(user as Parameters<typeof setUser>[0])
    setAuthError(null)
    toast({ title, detail: `Welcome back, ${user.name ?? user.email}`, tone: 'success' })
    navigate('/workspace', { replace: true })
  }

  const fail = (err: unknown, title: string) => {
    const msg = err instanceof Error ? err.message : 'Login failed'
    setError(msg)
    setAuthError(msg)
    toast({ title, detail: msg, tone: 'error' })
  }

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

  /** Local development only: mint via the backend dev-token endpoint. */
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

  /** Production: Supabase Auth email/password (sign-in or sign-up). */
  const handleSupabaseAuth = async () => {
    if (!email.trim() || !password) {
      setError('Enter your email and password.')
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const session =
        mode === 'signin'
          ? await supabaseSignIn(email, password)
          : await supabaseSignUp(email, password, name)
      const user = await loginWithToken(session.access_token)
      finishLogin(user, mode === 'signin' ? 'Signed in' : 'Account created')
    } catch (err) {
      fail(err, mode === 'signin' ? 'Sign-in failed' : 'Sign-up failed')
    } finally {
      setIsLoading(false)
    }
  }

  /** Production fallback: validate + store a user-supplied JWT via /auth/me. */
  const handleTokenLogin = async () => {
    if (!pastedToken.trim()) {
      setError('Paste an access token first.')
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const user = await loginWithToken(pastedToken)
      setPastedToken('')
      setShowTokenForm(false)
      finishLogin(user, 'Signed in')
    } catch (err) {
      fail(err, 'Token sign-in failed')
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

          {/* ── Production: Supabase email/password ── */}
          {supabaseReady && (
            <>
              <div className="relative py-1">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full" style={{ borderTop: '1px solid var(--as-border)' }} />
                </div>
                <div className="relative flex justify-center text-[12.5px]">
                  <span
                    className="px-3"
                    style={{ background: 'var(--as-glass-bg)', color: 'var(--as-text-3)' }}
                  >
                    {mode === 'signin' ? 'sign in with email' : 'create an account'}
                  </span>
                </div>
              </div>

              {mode === 'signup' && (
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Display name (optional)"
                  autoComplete="name"
                  style={inputStyle}
                />
              )}
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                type="email"
                autoComplete="email"
                style={inputStyle}
              />
              <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                type="password"
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                onKeyDown={(e) => { if (e.key === 'Enter') void handleSupabaseAuth() }}
                style={inputStyle}
              />
              <button
                onClick={handleSupabaseAuth}
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-3 px-4 py-3.5 rounded-2xl border font-medium text-[15px] transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:-translate-y-0.5 active:translate-y-0"
                style={{
                  background: 'color-mix(in oklch, var(--as-accent) 10%, transparent)',
                  borderColor: 'color-mix(in oklch, var(--as-accent) 30%, transparent)',
                  color: 'var(--as-accent-hi)',
                }}
              >
                {isLoading ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /><span>{mode === 'signin' ? 'Signing in…' : 'Creating account…'}</span></>
                ) : (
                  <><LogIn className="w-4 h-4" /><span>{mode === 'signin' ? 'Sign in' : 'Create account'}</span></>
                )}
              </button>
              <button
                onClick={() => setMode(mode === 'signin' ? 'signup' : 'signin')}
                className="w-full text-center text-[13px] underline underline-offset-2 transition-colors"
                style={{ color: 'var(--as-text-3)' }}
              >
                {mode === 'signin' ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
              </button>
            </>
          )}

          {/* ── Production fallback: paste an access token ── */}
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

          {!showTokenForm ? (
            <button
              onClick={() => { setShowTokenForm(true); setError(null) }}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-2xl border font-medium text-[14px] transition-all hover:-translate-y-0.5 active:translate-y-0"
              style={{
                background: 'transparent',
                borderColor: 'var(--as-border)',
                color: 'var(--as-text-2)',
              }}
            >
              <KeyRound className="w-4 h-4" /><span>Use an existing access token</span>
            </button>
          ) : (
            <>
              <input
                value={pastedToken}
                onChange={(e) => setPastedToken(e.target.value)}
                placeholder="Paste your Supabase / Better Auth JWT"
                type="password"
                autoComplete="off"
                spellCheck={false}
                onKeyDown={(e) => { if (e.key === 'Enter') void handleTokenLogin() }}
                style={inputStyle}
              />
              <div className="flex gap-2">
                <button
                  onClick={handleTokenLogin}
                  disabled={isLoading}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-2xl border font-medium text-[14px] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{
                    background: 'color-mix(in oklch, var(--as-accent) 10%, transparent)',
                    borderColor: 'color-mix(in oklch, var(--as-accent) 30%, transparent)',
                    color: 'var(--as-accent-hi)',
                  }}
                >
                  {isLoading ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /><span>Verifying…</span></>
                  ) : (
                    <><KeyRound className="w-4 h-4" /><span>Verify & sign in</span></>
                  )}
                </button>
                <button
                  onClick={() => { setShowTokenForm(false); setPastedToken(''); setError(null) }}
                  className="px-4 py-3 rounded-2xl border text-[14px]"
                  style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-3)' }}
                >
                  Cancel
                </button>
              </div>
              <p className="text-[12.5px] leading-relaxed" style={{ color: 'var(--as-text-3)' }}>
                The token is validated against <span className="mono">GET /api/v1/auth/me</span> before
                it is accepted.
              </p>
            </>
          )}

          {/* Local dev only: dev-token minter */}
          {devAllowed && (
            <>
              <div className="relative py-1">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full" style={{ borderTop: '1px dashed var(--as-border)' }} />
                </div>
                <div className="relative flex justify-center text-[12.5px]">
                  <span
                    className="px-3"
                    style={{ background: 'var(--as-glass-bg)', color: 'var(--as-text-3)' }}
                  >
                    local dev only
                  </span>
                </div>
              </div>
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
            </>
          )}

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
            { icon: Shield, text: supabaseReady ? 'Production sign-in via Supabase Auth' : 'Bearer JWT verified by the backend' },
            { icon: User, text: 'Full access to all features' },
            { icon: Zap, text: 'No account required for guest demo' },
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
