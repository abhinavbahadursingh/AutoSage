/**
 * Minimal Supabase Auth (GoTrue) REST client — production auth path.
 *
 * The FastAPI backend verifies Supabase RS256 JWTs via JWKS
 * (SUPABASE_URL/auth/v1/.well-known/jwks.json) and lazily provisions the
 * local user row from the token claims, so a Supabase session token works
 * as the Bearer token for every /api/v1 request including GET /auth/me.
 *
 * Implemented with plain fetch (no new dependencies). Only active when
 * VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY are configured.
 */
import type { ApiUser } from './api'

const SUPABASE_URL = ((import.meta.env.VITE_SUPABASE_URL as string | undefined) || '').trim().replace(/\/$/, '')
const SUPABASE_ANON_KEY = ((import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined) || '').trim()

export function isSupabaseConfigured(): boolean {
  return SUPABASE_URL.length > 0 && SUPABASE_ANON_KEY.length > 0
}

export interface SupabaseSession {
  access_token: string
  user: ApiUser
}

interface GoTrueUser {
  id: string
  email?: string | null
  confirmed_at?: string | null
  email_confirmed_at?: string | null
  created_at?: string
  user_metadata?: Record<string, unknown> | null
}

interface GoTrueTokenResponse {
  access_token?: string
  user?: GoTrueUser | null
  session?: { access_token?: string; user?: GoTrueUser | null } | null
  msg?: string
  message?: string
  error_description?: string
}

function toApiUser(u: GoTrueUser): ApiUser {
  const meta = u.user_metadata ?? {}
  const name =
    (typeof meta.name === 'string' && meta.name) ||
    (typeof meta.full_name === 'string' && meta.full_name) ||
    null
  const image = typeof meta.avatar_url === 'string' ? (meta.avatar_url as string) : null
  return {
    id: u.id,
    email: u.email ?? '',
    name,
    image,
    email_verified: Boolean(u.confirmed_at ?? u.email_confirmed_at),
    created_at: u.created_at ?? new Date().toISOString(),
  }
}

async function goTrue(path: string, body: Record<string, unknown>): Promise<GoTrueTokenResponse> {
  const res = await fetch(`${SUPABASE_URL}/auth/v1/${path}`, {
    method: 'POST',
    headers: {
      apikey: SUPABASE_ANON_KEY,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  let data: GoTrueTokenResponse = {}
  try {
    data = (await res.json()) as GoTrueTokenResponse
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const detail =
      data.error_description || data.msg || data.message || `Supabase Auth failed (HTTP ${res.status})`
    throw new Error(detail)
  }
  return data
}

function sessionFrom(data: GoTrueTokenResponse): SupabaseSession {
  const accessToken = data.access_token ?? data.session?.access_token ?? ''
  const rawUser = data.user ?? data.session?.user ?? null
  if (!accessToken || !rawUser) {
    throw new Error(
      'Sign-up succeeded but no session was issued (email confirmation may be required — check your inbox, then sign in).',
    )
  }
  return { access_token: accessToken, user: toApiUser(rawUser) }
}

/** Email + password sign-in (production). */
export async function supabaseSignIn(email: string, password: string): Promise<SupabaseSession> {
  if (!isSupabaseConfigured()) throw new Error('Supabase Auth is not configured.')
  const data = await goTrue('token?grant_type=password', { email: email.trim(), password })
  return sessionFrom(data)
}

/** Email + password sign-up (production). May require email confirmation. */
export async function supabaseSignUp(
  email: string,
  password: string,
  name?: string,
): Promise<SupabaseSession> {
  if (!isSupabaseConfigured()) throw new Error('Supabase Auth is not configured.')
  const data = await goTrue('signup', {
    email: email.trim(),
    password,
    data: name?.trim() ? { name: name.trim() } : {},
  })
  return sessionFrom(data)
}

/**
 * Anonymous demo sign-in (production Demo Login).
 * Requires "Allow anonymous sign-ins" enabled on the Supabase project.
 */
export async function supabaseAnonymousSignIn(): Promise<SupabaseSession> {
  if (!isSupabaseConfigured()) throw new Error('Supabase Auth is not configured.')
  const data = await goTrue('signup', { data: { name: 'Guest User' } })
  return sessionFrom(data)
}
