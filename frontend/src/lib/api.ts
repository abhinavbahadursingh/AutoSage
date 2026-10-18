/**
 * Centralized AutoSage API client.
 *
 * Base URL resolution (first non-empty wins):
 *  1. VITE_API_BASE_URL (e.g. `/api/v1` for the Vite dev proxy, or an
 *     absolute `https://<backend>/api/v1` in production)
 *  2. VITE_BACKEND_ORIGIN + `/api/v1` (production: `VITE_BACKEND_ORIGIN`
 *     is the Render backend origin, e.g. `https://autosage-1.onrender.com`)
 *  3. `/api/v1` (same-origin fallback)
 *
 * Auth uses the backend's existing JWT Bearer mechanism: every request sends
 * `Authorization: Bearer <token>` where the token is a Supabase Auth JWT
 * (RS256, verified via JWKS) or a Better Auth HS256 JWT. In local
 * development only, the backend's dev-token minter may be used instead —
 * the production backend returns 404 for it by design, so this client never
 * calls it outside local dev (see isDevTokenAllowed).
 */

const TOKEN_KEY = 'as_access_token'
const USER_KEY = 'as_auth_user'

function resolveApiBase(): string {
  const explicit = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim()
  if (explicit) return explicit.replace(/\/$/, '')
  const origin = (import.meta.env.VITE_BACKEND_ORIGIN as string | undefined)?.trim()
  if (origin) return `${origin.replace(/\/$/, '')}/api/v1`
  return '/api/v1'
}

const API_BASE = resolveApiBase()
const WS_BASE = ((import.meta.env.VITE_WS_BASE_URL as string | undefined) || '').trim()

/**
 * Whether the local-dev token minter (POST /auth/dev-token) may be used.
 *
 * True only for local development: explicit opt-in via
 * VITE_ALLOW_DEV_TOKEN=true, or when the page is served from localhost
 * (and not explicitly disabled). Production builds served from any other
 * host never touch the dev-token endpoint — the production backend answers
 * 404 there by design.
 */
export function isDevTokenAllowed(): boolean {
  const flag = (import.meta.env.VITE_ALLOW_DEV_TOKEN as string | undefined)?.trim().toLowerCase()
  if (flag === 'true') return true
  if (flag === 'false') return false
  if (typeof window !== 'undefined') {
    const host = window.location.hostname
    if (host === 'localhost' || host === '127.0.0.1' || host === '[::1]') return true
  }
  return false
}

/** Error thrown when code asks for a dev token where it is not allowed. */
export function devTokenDisabledError(): ApiError {
  return new ApiError(
    404,
    {
      detail:
        'Demo/dev login is disabled in this environment: the backend only mints dev tokens for local development. Sign in with your production account instead.',
    },
    '/auth/dev-token',
  )
}

export interface ApiUser {
  id: string
  email: string
  name: string | null
  image: string | null
  email_verified: boolean
  created_at: string
}

export interface DevTokenResponse {
  access_token: string
  token_type: string
  user: ApiUser
}

export interface Paged<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface WorkspaceRead {
  id: string
  owner_id: string
  name: string
  description: string | null
  meta: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type ApiExperimentStatus =
  | 'CREATED'
  | 'QUEUED'
  | 'RUNNING'
  | 'COMPLETED'
  | 'FAILED'
  | 'RETRYING'
  | 'CANCELLED'

export interface ExperimentRead {
  id: string
  workspace_id: string
  name: string
  description: string | null
  status: ApiExperimentStatus
  config: Record<string, unknown>
  result_summary: Record<string, unknown>
  error_detail: string | null
  retry_count: number
  max_retries: number
  celery_task_id: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface ExperimentCreate {
  name: string
  description?: string
  workspace_id: string
  config?: Record<string, unknown>
  max_retries?: number
}

export interface HealthResponse {
  status: string
  service: string
  version: string
  environment: string
  checks: Record<string, string>
}

export interface MemorySearchResult {
  id: string
  memory_type: string
  task_type: string
  solution_strategy: string
  achieved_metric_value: number | null
  metric_name: string | null
  similarity_score: number
  ranking_score: number | null
  rank_factors: Record<string, number> | null
  created_at: string | null
}

export interface MemorySearchResponse {
  results: MemorySearchResult[]
  query: string
}

export interface EvidenceTrailResponse {
  run_id: string
  nodes: unknown[]
  edges: unknown[]
}

export interface EvidencePiece {
  content: string
  source_id: string
  source_type: string
  title: string | null
  url: string | null
  snippet: string | null
  credibility_score: number
  metadata: Record<string, unknown>
  retrieved_at: string
}

export interface VerificationResult {
  claim_id: string
  claim_text: string
  claim_type: string
  status: 'VERIFIED' | 'CONFLICT' | 'REJECTED' | 'UNVERIFIED' | 'ABSTAIN'
  confidence_score: number
  supporting_evidence: EvidencePiece[]
  contradicting_evidence: EvidencePiece[]
  reasoning: string
  verified_at: string
}

export interface VerificationResponse {
  results: VerificationResult[]
  overall_status: string
  overall_confidence: number
  total_claims: number
  verified_count: number
  conflict_count: number
  rejected_count: number
  unverified_count: number
}

export interface EvidenceSourceInfo {
  source_id: string
  source_type: string
  credibility_score: number
  last_updated: string | null
}

/** Generic JSON object, used for backend payloads with free-form keys. */
export type Dict<V = unknown> = Record<string, V>

// ── Fresh Experiment Objective Verification ──────────────────────────────────
//
// Four canonical objectives and a fixed stage order, both served by the backend
// so the client never hardcodes them. Mirrors
// app/schemas/objective_verification.py.

/**
 * Terminal state of one deterministic check.
 *
 * NOT_VERIFIED is deliberately not a pass: it means the evidence a check
 * needed does not exist. On a fresh session that is the normal case for
 * everything depending on a training run, because verification never trains.
 */
export type ObjectiveCheckStatus = 'PASS' | 'FAIL' | 'NOT_VERIFIED' | 'BLOCKED'

/** Lifecycle of one verification stage. */
export type ObjectiveStageStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'PASSED'
  | 'FAILED'
  | 'NOT_VERIFIED'
  | 'BLOCKED'

export interface ObjectiveCheckDefinition {
  id: string
  title: string
  description: string
  /** What must be true for this check to PASS. */
  expected: string
  /** What record/artifact backs the verdict when it does. */
  evidence_source: string
}

export interface ObjectiveDefinition {
  id: string
  number: number
  title: string
  statement: string
  checks: ObjectiveCheckDefinition[]
}

export interface ObjectiveCheckResult {
  check_id: string
  title: string
  status: ObjectiveCheckStatus
  /** What the check expected, echoed so both sides are visible. */
  expected: string
  /** What actually happened. */
  actual: string
  /** What was observed, quoted verbatim. */
  evidence: string[]
  reasoning: string
  /** 0..1, derived deterministically from gathered evidence. */
  confidence: number
  artifact: string
  checked_at: string
  /**
   * Evidence kind examined: 'source' (repository), 'probe' (synthetic
   * in-memory data), 'session' (this session's database records),
   * 'generated' (code-generation output, never executed) or 'empirical'
   * (a real measured run).
   */
  category?: string
  /**
   * Strength of that evidence: 'source' | 'config' | 'generated' | 'runtime'.
   * A source-level PASS is not proof that a specific generated decision is
   * correct — runtime checks are exactly the ones a fresh session cannot meet.
   */
  verification_level?: string
}

export interface ObjectiveResult {
  id: string
  number: number
  title: string
  statement: string
  status: ObjectiveStageStatus
  confidence: number
  checks: ObjectiveCheckResult[]
  started_at: string | null
  completed_at: string | null
}

/**
 * One design decision produced during code generation. Rationale, confidence
 * and source are optional on purpose: they are only present when the
 * generating model genuinely produced them, never filled in with a default.
 */
export interface ObjectiveDecisionRecord {
  category: string
  decision: string
  rationale?: string | null
  confidence?: number | null
  source?: string | null
  alternatives?: string[]
  assumptions?: string[]
}

/** The design summary the individual decisions belong to. */
export interface ObjectiveDesignRecord {
  algorithm?: string | null
  hyperparameters?: Record<string, unknown>
  metrics?: Record<string, unknown>
  validation_strategy?: string | null
  assumptions?: string[]
  alternatives?: string[]
  decisions?: ObjectiveDecisionRecord[]
}

export interface ObjectiveVerificationReport {
  run_id: string
  experiment_id: string
  problem_statement: string
  dataset_name: string
  config: Dict
  objectives: ObjectiveResult[]
  overall_status: ObjectiveStageStatus
  overall_confidence: number
  /** Check tallies by status, so the verdict is auditable at a glance. */
  totals: Record<string, number>
  /** Check tallies by evidence category (source/probe/session/generated/...). */
  evidence_categories?: Record<string, number>
  /** Check tallies by verification level (source/config/generated/runtime). */
  verification_levels?: Record<string, number>
  code_generation_status?: string
  code_generation_message?: string
  /** Design summary + decisions produced with the code (design-time only). */
  design?: ObjectiveDesignRecord
  decisions?: ObjectiveDecisionRecord[]
  started_at: string | null
  completed_at: string | null
}

/** One streamed progress frame. */
export interface ObjectiveStageUpdate {
  run_id: string
  stage: string
  status: ObjectiveStageStatus
  message: string
  check: ObjectiveCheckResult | null
  objective_id: string | null
  emitted_at: string
  /** Stage payload — code generation carries files, activity and decisions. */
  payload?: Dict
}

/**
 * Body for POST /objective-verification/sessions. `problem_statement` is
 * required: there is no previous experiment to fall back to. Dataset, task
 * type and metric are optional — this is a design-time audit.
 */
export interface FreshSessionCreate {
  workspace_id: string
  problem_statement: string
  dataset_name?: string
  target_column?: string | null
  task_type?: string
  primary_metric?: string | null
}

/** POST /sessions response — the run id arrives immediately. */
export interface FreshSessionAccepted {
  run_id: string
  experiment_id: string
  status: ObjectiveStageStatus
  stream_url: string
}

/**
 * GET /objective-verification/sessions — one cheap listing row for a session
 * the caller created. Discovery only: the verbatim problem statement plus
 * lifecycle fields; frames and full report come from the detail endpoint.
 * Mirrors app/schemas/objective_verification.py SessionSummary.
 */
export interface ObjectiveSessionSummary {
  run_id: string
  experiment_id: string
  linked_experiment_id: string | null
  /** What the caller asked, verbatim as submitted. */
  problem_statement: string
  dataset_name: string
  config: Dict
  status: string
  overall_status: string | null
  overall_confidence: number | null
  decision_count: number
  stage_count: number
  created_at: string | null
  completed_at: string | null
  error: string | null
}

/** GET /sessions/{run_id} — reconnect path, replays stored frames. */
export interface ObjectiveSessionState {
  run_id: string
  experiment_id: string
  linked_experiment_id?: string | null
  status: string
  problem_statement: string
  dataset_name: string
  config: Dict
  updates: ObjectiveStageUpdate[]
  report: ObjectiveVerificationReport | null
  /** Code-generation artifacts, readable without re-parsing the frames. */
  generated_files?: { name: string; language: string; content: string }[]
  activity_log?: string[]
  design?: ObjectiveDesignRecord
  decisions?: ObjectiveDecisionRecord[]
  code_generation_status?: string | null
  code_generation_message?: string | null
  overall_status: string | null
  overall_confidence: number | null
  error: string | null
  running: boolean
  created_at: string | null
  completed_at: string | null
}

/** One dataset the caller may submit for a fresh session. */
export interface SessionDataset {
  name: string
  size_bytes: number | null
  dataset_id: string | null
}

export interface ProjectResponse {
  id: string
  user_id: string
  name: string
  description: string | null
  created_at: string
}

/** Answer from GET /datasets/resolve — does this filename exist for me? */
export interface DatasetResolveResponse {
  name: string
  available: boolean
  /** 'upload_dir' | 'registry' when available, else null. */
  source: 'upload_dir' | 'registry' | null
  size_bytes: number | null
  dataset_id?: string
}

/** Answer from POST /datasets/upload. */
export interface DatasetUploadResponse {
  name: string
  size_bytes: number
  path: string
  original_filename: string | null
  content_type: string | null
  status: string
}

export interface StorageStats {
  total_files: number
  total_bytes: number
  by_category: Record<string, number>
}

export interface ReproducibilityRecordRead {
  id: string
  experiment_id: string
  ml_run_id: string | null
  dataset_id: string | null
  dataset_sha256: string | null
  dataset_size_bytes: number | null
  dataset_rows: number | null
  dataset_columns: number | null
  model_family: string
  model_name: string | null
  final_metrics: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface SandboxExecuteResponse {
  success: boolean
  job_id: string
  metrics: Record<string, number>
  artifacts: string[]
  stdout: string
  stderr: string
  error_type: string | null
  error_message: string | null
  duration_sec: number
  exit_code: number | null
}

export interface SandboxStatusResponse {
  available: boolean
  error: string | null
  config?: {
    image_tag: string
    cpu_limit: number
    memory_limit: string
    timeout_sec: number
    workspace_size: string
    pids_limit: number
    readonly_rootfs: boolean
  }
}

export interface LlmStatus {
  fast_model: string
  reasoning_model: string
  default_model: string
  providers: string[]
  fallback_order: string[]
}

export interface LlmCheckResult {
  ok: boolean
  model: string
  provider: string | null
  latency_ms: number | null
  sample: string | null
  error: string | null
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string | null
  readonly path: string | null
  readonly detail: unknown

  constructor(status: number, detail: unknown, path: string | null) {
    const message = friendlyErrorMessage(status, detail)
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = extractCode(detail)
    this.path = path
    this.detail = detail
  }
}

function extractCode(detail: unknown): string | null {
  if (detail && typeof detail === 'object' && 'code' in detail) {
    const c = (detail as { code?: unknown }).code
    return typeof c === 'string' ? c : null
  }
  return null
}

function friendlyErrorMessage(status: number, detail: unknown): string {
  if (detail && typeof detail === 'object') {
    const d = detail as { detail?: unknown; message?: unknown }
    if (typeof d.detail === 'string' && d.detail) return d.detail
    if (Array.isArray(d.detail)) {
      const parts = d.detail
        .map((item) => {
          if (item && typeof item === 'object' && 'msg' in item) {
            const loc = (item as { loc?: unknown }).loc
            const where = Array.isArray(loc) ? loc.filter((x) => x !== 'body').join('.') : ''
            const msg = String((item as { msg?: unknown }).msg ?? '')
            return where ? `${where}: ${msg}` : msg
          }
          return String(item)
        })
        .filter(Boolean)
      if (parts.length) return parts.join('; ')
    }
    if (typeof d.message === 'string' && d.message) return d.message
  }
  if (status === 401) return 'Not authenticated. Sign in again and retry.'
  if (status === 403) return 'You do not have access to this resource.'
  if (status === 404) return 'Resource not found.'
  if (status === 409) return 'Operation conflicts with the current experiment state.'
  if (status === 422) return 'The request was rejected by the server validation.'
  if (status === 429) return 'Too many requests. Slow down and try again.'
  if (status === 503) return 'Backend service is temporarily unavailable.'
  if (status >= 500) return 'Server error. Please try again shortly.'
  return `Request failed (HTTP ${status}).`
}

export function getToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token)
    else window.localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* ignore quota / private mode */
  }
}

export function getCachedUser(): ApiUser | null {
  try {
    const raw = window.localStorage.getItem(USER_KEY)
    if (!raw) return null
    return JSON.parse(raw) as ApiUser
  } catch {
    return null
  }
}

export function setCachedUser(user: ApiUser | null): void {
  try {
    if (user) window.localStorage.setItem(USER_KEY, JSON.stringify(user))
    else window.localStorage.removeItem(USER_KEY)
  } catch {
    /* ignore */
  }
}

type TokenRefresh = Promise<string>

let inflightToken: TokenRefresh | null = null

/**
 * Mint a backend dev JWT.
 *
 * LOCAL DEVELOPMENT ONLY. The production backend (APP_ENV=production)
 * intentionally answers 404 here, so this function refuses to issue the
 * request unless isDevTokenAllowed() — production callers get a clear
 * local error instead of a confusing HTTP 404.
 */
export async function mintDevToken(): Promise<DevTokenResponse> {
  if (!isDevTokenAllowed()) throw devTokenDisabledError()
  const res = await fetch(`${API_BASE}/auth/dev-token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  if (!res.ok) {
    let detail: unknown = null
    try {
      detail = await res.json()
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail, '/auth/dev-token')
  }
  return (await res.json()) as DevTokenResponse
}

/**
 * Return the stored Bearer token, minting a dev token only in local dev.
 * In production with no stored token this throws a 401 "sign in required"
 * error instead of calling the (404) dev-token endpoint.
 */
export async function ensureToken(force = false): Promise<string> {
  if (!force) {
    const existing = getToken()
    if (existing) return existing
  }
  if (!isDevTokenAllowed()) {
    throw new ApiError(
      401,
      { detail: 'Not authenticated. Sign in to continue.' },
      '/auth/dev-token',
    )
  }
  if (!inflightToken) {
    inflightToken = mintDevToken()
      .then((data) => {
        setToken(data.access_token)
        setCachedUser(data.user)
        return data.access_token
      })
      .finally(() => {
        inflightToken = null
      })
  }
  return inflightToken
}

/**
 * Production login with an already-obtained JWT (Supabase Auth / Better
 * Auth session token, or a token pasted by the operator). The token is
 * stored and immediately validated against GET /auth/me so a bad token
 * never leaves the login screen looking valid.
 */
export async function loginWithToken(accessToken: string): Promise<ApiUser> {
  const token = accessToken.trim()
  if (!token) {
    throw new ApiError(401, { detail: 'No token provided.' }, '/auth/me')
  }
  setToken(token)
  try {
    const me = await request<ApiUser>('/auth/me')
    setCachedUser(me)
    return me
  } catch (err) {
    setToken(null)
    setCachedUser(null)
    throw err
  }
}

function resolveUrl(path: string): string {
  if (path.startsWith('http://') || path.startsWith('https://')) return path
  if (path === '/health' || path.startsWith('/health?')) return path
  const suffix = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE.replace(/\/$/, '')}${suffix}`
}

async function request<T>(
  path: string,
  init: RequestInit & { auth?: boolean; retried?: boolean } = {},
): Promise<T> {
  const { auth = true, retried = false, headers, ...rest } = init
  const finalUrl = resolveUrl(path)

  const h = new Headers(headers)
  if (!h.has('Content-Type') && rest.body && !(rest.body instanceof FormData)) {
    h.set('Content-Type', 'application/json')
  }
  if (auth) {
    const token = await ensureToken()
    h.set('Authorization', `Bearer ${token}`)
  }

  let res: Response
  try {
    res = await fetch(finalUrl, { ...rest, headers: h })
  } catch (err) {
    throw new ApiError(
      0,
      { detail: err instanceof Error ? err.message : 'Network error' },
      finalUrl,
    )
  }

  if (res.status === 204) return undefined as T

  let body: unknown = null
  const text = await res.text()
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = { detail: text }
    }
  }

  if (!res.ok) {
    if (res.status === 401 && auth && !retried) {
      // Local dev: the dev-token minter can silently re-issue a token.
      // Production: there is nothing to silently re-mint (dev-token is 404
      // by design), so drop the stale token and surface the 401 — the
      // login screen owns re-authentication.
      if (isDevTokenAllowed()) {
        setToken(null)
        try {
          await ensureToken(true)
        } catch {
          /* fall through to throw */
        }
        return request<T>(path, { ...init, retried: true })
      }
      setToken(null)
    }
    throw new ApiError(res.status, body, finalUrl)
  }

  return body as T
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

/**
 * Console tracer shared with the Objectives page. Both use the `[G&V]`
 * prefix so the whole Generate & Verify flow reads as one filtered trail in
 * the browser console.
 */
function trace(...args: unknown[]): void {
  console.log('[G&V]', new Date().toISOString().slice(11, 23), ...args)
}

function traceError(...args: unknown[]): void {
  console.error('[G&V]', new Date().toISOString().slice(11, 23), ...args)
}

/**
 * Parse one SSE frame and route it to the matching handler.
 *
 * Kept separate from `streamObjectiveSession` so the frame grammar lives in one
 * place: `event:` names the channel and `data:` carries the JSON payload.
 * Comment-only keep-alive frames are ignored.
 */
function dispatchObjectiveFrame(
  frame: string,
  handlers: {
    onStage?: (update: ObjectiveStageUpdate) => void
    onReport?: (report: ObjectiveVerificationReport) => void
    onError?: (message: string) => void
  },
): void {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of frame.split('\n')) {
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!dataLines.length) return

  let payload: unknown
  try {
    payload = JSON.parse(dataLines.join('\n'))
  } catch {
    traceError('malformed SSE frame', { event, raw: frame })
    handlers.onError?.('Received a malformed progress frame')
    return
  }

  trace('raw SSE frame', { event }, payload)

  if (event === 'stage') handlers.onStage?.(payload as ObjectiveStageUpdate)
  else if (event === 'report') handlers.onReport?.(payload as ObjectiveVerificationReport)
  else if (event === 'error') {
    handlers.onError?.((payload as { message?: string })?.message ?? 'Verification failed')
  }
}

export const api = {
  base: API_BASE,

  health: () => request<HealthResponse>('/health', { auth: false }),

  /**
   * App-start authentication.
   * - A stored token is validated via GET /auth/me (works in every env).
   * - No token + local dev: mint a dev token (historical local behavior).
   * - No token + production: throw "sign in required" — never call the
   *   dev-token endpoint (production answers 404 by design).
   * - Stored-but-expired token (401): local dev re-mints, production
   *   clears the token and throws so the login screen takes over.
   */
  async bootstrapAuth(): Promise<ApiUser> {
    const stored = getToken()
    if (!stored && !isDevTokenAllowed()) {
      throw new ApiError(
        401,
        { detail: 'Not authenticated. Sign in to continue.' },
        '/auth/me',
      )
    }
    await ensureToken()
    try {
      const me = await request<ApiUser>('/auth/me')
      setCachedUser(me)
      return me
    } catch (err) {
      if (err instanceof ApiError && err.status === 401 && isDevTokenAllowed()) {
        const minted = await mintDevToken()
        setToken(minted.access_token)
        setCachedUser(minted.user)
        return minted.user
      }
      if (err instanceof ApiError && err.status === 401) {
        setToken(null)
        setCachedUser(null)
      }
      throw err
    }
  },

  me: () => request<ApiUser>('/auth/me'),

  listWorkspaces: (page = 1, pageSize = 20) =>
    request<Paged<WorkspaceRead>>(`/workspaces${qs({ page, page_size: pageSize })}`),

  createWorkspace: (payload: { name: string; description?: string }) =>
    request<WorkspaceRead>('/workspaces', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listExperiments: (
    params: { page?: number; page_size?: number; workspace_id?: string; status?: string } = {},
  ) =>
    request<Paged<ExperimentRead>>(
      `/experiments${qs({
        page: params.page ?? 1,
        page_size: params.page_size ?? 100,
        workspace_id: params.workspace_id,
        status: params.status,
      })}`,
    ),

  getExperiment: (id: string) => request<ExperimentRead>(`/experiments/${id}`),

  createExperiment: (payload: ExperimentCreate) =>
    request<ExperimentRead>('/experiments', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateExperiment: (
    id: string,
    payload: Partial<Pick<ExperimentCreate, 'name' | 'description' | 'config' | 'max_retries'>>,
  ) =>
    request<ExperimentRead>(`/experiments/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteExperiment: (id: string) =>
    request<void>(`/experiments/${id}`, { method: 'DELETE' }),

  startExperiment: (id: string) =>
    request<ExperimentRead>(`/experiments/${id}/start`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  cancelExperiment: (id: string) =>
    request<ExperimentRead>(`/experiments/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  listProjects: () => request<ProjectResponse[]>('/projects'),

  listDatasets: (projectId: string) =>
    request<unknown[]>(`/projects/${projectId}/datasets`),

  /**
   * Preflight probe run before a pipeline is queued. Returns
   * `{ available: false }` rather than throwing when the dataset is missing,
   * so callers can branch on the flag instead of catching.
   */
  resolveDataset: (name: string, workspaceId?: string) =>
    request<DatasetResolveResponse>(`/datasets/resolve${qs({ name, workspace_id: workspaceId })}`),

  /** Upload a dataset file so the worker can resolve it by filename. */
  uploadDataset: (file: File, workspaceId?: string) => {
    const form = new FormData()
    form.append('file', file)
    const query = qs({ workspace_id: workspaceId })
    return request<DatasetUploadResponse>(`/datasets/upload${query}`, {
      method: 'POST',
      body: form,
    })
  },

  searchMemory: (query: string) =>
    request<MemorySearchResponse>(`/memory/search${qs({ query })}`),

  getEvidenceTrail: (runId: string) =>
    request<EvidenceTrailResponse>(`/runs/${runId}/evidence`),

  listEvidenceSources: () => request<EvidenceSourceInfo[]>('/verification/sources'),

  verifyExperiment: (experimentId: string, agentName?: string) =>
    request<VerificationResponse>('/verification/experiment', {
      method: 'POST',
      body: JSON.stringify(
        agentName ? { experiment_id: experimentId, agent_name: agentName } : { experiment_id: experimentId },
      ),
    }),

  searchEvidence: (query: string, limit = 20) =>
    request<{
      query: string
      pieces: EvidencePiece[]
      total_found: number
      search_metadata: Record<string, unknown>
    }>('/verification/evidence/search', {
      method: 'POST',
      body: JSON.stringify({ query, limit }),
    }),

  // ── Fresh Experiment Objective Verification ───────────────────────────────

  /**
   * The fixed four-objective graph definition.
   * Node identity, ordering and check identity all come from here, never from
   * a client copy that could drift.
   */
  listObjectives: () => request<ObjectiveDefinition[]>('/objective-verification/objectives'),

  /** The fixed stage order: input -> objective_1..4 -> report. */
  objectiveStages: () => request<{ stages: string[] }>('/objective-verification/stages'),

  /** Datasets the caller may submit for a fresh session. */
  listSessionDatasets: (workspaceId?: string) =>
    request<SessionDataset[]>(`/objective-verification/datasets${qs({ workspace_id: workspaceId })}`),

  /**
   * Start a brand-new verification session. Returns the run id immediately —
   * this never blocks on the verification itself, and it never reuses a
   * previous experiment.
   */
  createObjectiveSession: (payload: FreshSessionCreate) =>
    request<FreshSessionAccepted>('/objective-verification/sessions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** Reconnect path: accumulated frames + report for a known run. */
  getObjectiveSession: (runId: string) =>
    request<ObjectiveSessionState>(
      `/objective-verification/sessions/${encodeURIComponent(runId)}`,
    ),

  /**
   * The caller's recent verification sessions, newest first. Cheap listing
   * rows used for discovery (Project Summary); no frames or report payload.
   */
  listObjectiveSessions: (limit = 20) =>
    request<ObjectiveSessionSummary[]>(
      `/objective-verification/sessions${qs({ limit })}`,
    ),

  /** Link a completed pipeline experiment to a verification session. */
  linkExperiment: (runId: string, experimentId: string) =>
    request<{ run_id: string; linked_experiment_id: string; status: string }>(
      `/objective-verification/sessions/${encodeURIComponent(runId)}/link-experiment`,
      {
        method: 'POST',
        body: JSON.stringify({ experiment_id: experimentId }),
      },
    ),

  /**
   * Subscribe to a session's progress over SSE.
   *
   * Returns an unsubscribe function. Frames are persisted server-side as they
   * are emitted, so a client that subscribes late (or reconnects) replays
   * everything it missed rather than restarting the run.
   *
   * The raw `fetch` + `ReadableStream` path is used rather than `EventSource`
   * because the stream needs the same Bearer token as every other call, and
   * `EventSource` cannot set request headers.
   */
  streamObjectiveSession: (
    runId: string,
    handlers: {
      onStage?: (update: ObjectiveStageUpdate) => void
      onReport?: (report: ObjectiveVerificationReport) => void
      onError?: (message: string) => void
      onOpen?: () => void
      /** Called when the stream ends normally (server closed the connection)
        without an error. The page can use this to reconnect or fall back to
        polling the session state API. */
      onEnd?: () => void
    },
  ): (() => void) => {
    const controller = new AbortController()
    let closed = false
    let ended = false

    void (async () => {
      try {
        const token = await ensureToken()
        const url = resolveUrl(
          `/objective-verification/sessions/${encodeURIComponent(runId)}/stream`,
        )
        trace('opening SSE connection', { run_id: runId, url })
        const response = await fetch(url, {
          headers: { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' },
          signal: controller.signal,
        })
        if (!response.ok || !response.body) {
          traceError('SSE connection rejected', { run_id: runId, status: response.status })
          handlers.onError?.(`Stream failed (HTTP ${response.status})`)
          return
        }
        trace('SSE connection established', { run_id: runId, status: response.status })
        handlers.onOpen?.()

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (!closed) {
          const { done, value } = await reader.read()
          if (done) {
            trace('SSE stream ended (reader done)', { run_id: runId })
            ended = true
            break
          }
          buffer += decoder.decode(value, { stream: true })

          // SSE frames are separated by a blank line.
          let boundary = buffer.indexOf('\n\n')
          while (boundary !== -1) {
            const frame = buffer.slice(0, boundary)
            buffer = buffer.slice(boundary + 2)
            dispatchObjectiveFrame(frame, handlers)
            boundary = buffer.indexOf('\n\n')
          }
        }
        // Flush a trailing frame that arrived without its blank-line terminator.
        if (buffer.trim()) dispatchObjectiveFrame(buffer, handlers)

        // Stream ended normally (server closed it). Notify the page so it can
        // reconnect or fall back to polling — but only if we didn't just
        // receive a report or error (those already set terminal state).
        if (ended && !closed) {
          handlers.onEnd?.()
        }
      } catch (err) {
        if (!closed && !(err instanceof DOMException && err.name === 'AbortError')) {
          traceError('SSE stream failed', { run_id: runId, error: err })
          handlers.onError?.(err instanceof Error ? err.message : 'Stream failed')
        } else if (closed) {
          trace('SSE stream closed by client', { run_id: runId })
        }
      }
    })()

    return () => {
      closed = true
      controller.abort()
    }
  },

  storageStats: () => request<StorageStats>('/storage/stats'),

  listReproducibility: (params: { page?: number; page_size?: number; workspace_id?: string } = {}) =>
    request<Paged<ReproducibilityRecordRead>>(
      `/reproducibility${qs({
        page: params.page ?? 1,
        page_size: params.page_size ?? 20,
        workspace_id: params.workspace_id,
      })}`,
    ),

  getReproducibilityForExperiment: (experimentId: string) =>
    request<ReproducibilityRecordRead>(`/experiments/${experimentId}/reproducibility`),

  llmStatus: () => request<LlmStatus>('/llm/status'),

  llmCheck: (model?: string) =>
    request<LlmCheckResult>('/llm/check', {
      method: 'POST',
      body: JSON.stringify({ model: model || null }),
    }),

  llmSelect: (model: string) =>
    request<LlmStatus>('/llm/select', {
      method: 'POST',
      body: JSON.stringify({ model }),
    }),

  sandboxExecute: (payload: {
    script: string
    dataset_path?: string | null
    env_vars?: Record<string, string>
    mlflow_run_id?: string | null
  }) =>
    request<SandboxExecuteResponse>('/sandbox/execute', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  sandboxStatus: () => request<SandboxStatusResponse>('/sandbox/status'),

  // ── Pipeline Planner ──────────────────────────────────────────────────────

  generatePipelinePlan: (payload: {
    description: string
    dataset_name?: string
    target_column?: string
    task_type?: string
  }) =>
    request<{
      task_type: string
      target_metric: string
      complexity: string
      stages: Array<{
        id: string
        name: string
        agent: string
        role: string
        description: string
        inputs: string[]
        outputs: string[]
        estimated_duration: string
        optional: boolean
      }>
      edges: Array<{ from_stage: string; to_stage: string; label: string }>
      summary: string
      assumptions: string[]
      risks: string[]
      source: string
    }>('/pipeline/plan', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  pipelineStatus: () =>
    request<{ available: boolean; llm_available: boolean; fallback_enabled: boolean }>(
      '/pipeline/status',
    ),
}

/**
 * Resolve a WS URL for one experiment stream.
 *
 * Backend route is `/api/v1/experiments/{id}/ws` with `?token=` auth.
 * - VITE_WS_BASE_URL set (production: `wss://autosage-1.onrender.com`):
 *   treated as the backend origin, optionally with an API prefix path. A
 *   bare origin gains the `/api/v1` prefix automatically.
 * - Otherwise derived from the HTTP API base (dev proxy or absolute URL).
 */
export function experimentWsUrl(experimentId: string, token: string): string {
  const query = `?token=${encodeURIComponent(token)}`
  const streamPath = `/experiments/${experimentId}/ws${query}`

  const fromHttpBase = (base: string): string => {
    const trimmed = base.replace(/\/$/, '')
    if (trimmed.startsWith('/')) {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      return `${proto}//${window.location.host}${trimmed}${streamPath}`
    }
    const url = new URL(trimmed)
    const proto = url.protocol === 'https:' ? 'wss:' : 'ws:'
    const prefix = url.pathname.replace(/\/$/, '')
    return `${proto}//${url.host}${prefix}${streamPath}`
  }

  if (WS_BASE) {
    const trimmed = WS_BASE.replace(/\/$/, '')
    // Back-compat: a base that already points at an experiments stream path.
    if (trimmed.includes('/experiments/')) {
      const sep = trimmed.includes('?') ? '&' : '?'
      return `${trimmed}${sep}token=${encodeURIComponent(token)}`
    }
    try {
      const url = new URL(trimmed)
      const proto = url.protocol === 'https:' || url.protocol === 'wss:' ? 'wss:' : 'ws:'
      const path = url.pathname.replace(/\/$/, '')
      // Bare origin (or origin + non-API prefix): the API lives under /api/v1.
      const prefix = path === '' || path === '/' ? '/api/v1' : path
      return `${proto}//${url.host}${prefix}${streamPath}`
    } catch {
      // Non-absolute value: treat like the dev-proxy path form.
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const path = trimmed.startsWith('/') ? trimmed : `/${trimmed}`
      return `${proto}//${window.location.host}${path}${streamPath}`
    }
  }
  return fromHttpBase(API_BASE)
}

export function absoluteWsBase(): string | null {
  if (!WS_BASE) return null
  return WS_BASE.replace(/\/$/, '')
}
