/**
 * Shared demo/guest login helper (used by the Login page and the Home page
 * demo button). Callers must push the returned user into the store (setUser)
 * so ProtectedRoute passes immediately.
 *
 * Login path by environment (production never touches /auth/dev-token —
 * the production backend answers 404 there by design):
 *  1. Local dev (localhost or VITE_ALLOW_DEV_TOKEN=true): mint a 7-day
 *     guest session via the backend dev-token endpoint (unchanged behavior).
 *  2. Production + Supabase configured: anonymous sign-in via Supabase
 *     Auth. The Supabase JWT is verified by the backend (JWKS) and works
 *     for every /api/v1 request including GET /auth/me.
 *  3. Production without Supabase: throw a descriptive error (no confusing
 *     HTTP 404) directing the user to the Login page.
 */
import {
  api,
  isDevTokenAllowed,
  setToken,
  setCachedUser,
  loginWithToken,
  type ApiUser,
  type DevTokenResponse,
} from './api'
import { isSupabaseConfigured, supabaseAnonymousSignIn } from './supabaseAuth'

export const GUEST_EMAIL = 'guest@autosage.local'
export const GUEST_NAME = 'Guest User'

async function loginAsGuestViaDevToken(): Promise<ApiUser> {
  const res = await fetch(`${api.base}/auth/dev-token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: GUEST_EMAIL,
      name: GUEST_NAME,
      expires_in_minutes: 60 * 24 * 7,
    }),
  })

  if (!res.ok) {
    let detail = ''
    try {
      const body = (await res.json()) as { detail?: unknown; message?: unknown }
      if (typeof body.detail === 'string') detail = `: ${body.detail}`
      else if (typeof body.message === 'string') detail = `: ${body.message}`
    } catch {
      /* ignore */
    }
    throw new Error(`Failed to create guest session (HTTP ${res.status})${detail}`)
  }

  const data = (await res.json()) as DevTokenResponse
  setToken(data.access_token)
  setCachedUser(data.user)
  return data.user
}

export async function loginAsGuest(): Promise<ApiUser> {
  // 1. Local development: unchanged dev-token guest flow.
  if (isDevTokenAllowed()) {
    return loginAsGuestViaDevToken()
  }
  // 2. Production with Supabase: real anonymous session (backend-verified).
  if (isSupabaseConfigured()) {
    const session = await supabaseAnonymousSignIn()
    return loginWithToken(session.access_token)
  }
  // 3. Production without an IdP: fail loudly with guidance, not a 404.
  throw new Error(
    'Demo login is unavailable: production authentication (Supabase Auth) is not configured. ' +
      'Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY, or sign in on the Login page with an existing account.',
  )
}
