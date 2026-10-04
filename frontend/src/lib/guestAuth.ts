/**
 * Shared demo/guest login helper.
 *
 * Mints a 7-day guest session via the backend dev-token endpoint, persists
 * the token + cached user, and returns the user. Used by both the Login
 * page and the Home page demo button — callers must push the returned user
 * into the store (setUser) so ProtectedRoute passes immediately.
 */
import { api, setToken, setCachedUser, type ApiUser, type DevTokenResponse } from './api'

export async function loginAsGuest(): Promise<ApiUser> {
  const res = await fetch(`${api.base}/auth/dev-token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: 'guest@autosage.local',
      name: 'Guest User',
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
