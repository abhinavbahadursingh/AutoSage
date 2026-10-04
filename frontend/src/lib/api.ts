/**
 * Centralized AutoSage API client.
 *
 * Base URL comes from VITE_API_BASE_URL (defaults to the Vite proxy path
 * `/api/v1` so the browser never needs a hardcoded localhost origin).
 * Auth uses the backend's existing JWT Bearer mechanism (dev-token mint +
 * Authorization header) — no second auth system.
 */

const TOKEN_KEY = 'as_access_token'
const USER_KEY = 'as_auth_user'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '/api/v1'
const WS_BASE = (import.meta.env.VITE_WS_BASE_URL as string | undefined) || ''

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

export interface ProjectResponse {
  id: string
  user_id: string
  name: string
  description: string | null
  created_at: string
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

/** Mint a backend dev JWT (existing project auth path for local/dev). */
async function mintDevToken(): Promise<DevTokenResponse> {
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

export async function ensureToken(force = false): Promise<string> {
  if (!force) {
    const existing = getToken()
    if (existing) return existing
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
      setToken(null)
      try {
        await ensureToken(true)
      } catch {
        /* fall through to throw */
      }
      return request<T>(path, { ...init, retried: true })
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

export const api = {
  base: API_BASE,

  health: () => request<HealthResponse>('/health', { auth: false }),

  async bootstrapAuth(): Promise<ApiUser> {
    await ensureToken()
    try {
      const me = await request<ApiUser>('/auth/me')
      setCachedUser(me)
      return me
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        const minted = await mintDevToken()
        setToken(minted.access_token)
        setCachedUser(minted.user)
        return minted.user
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
}

/** Resolve a WS URL through the Vite proxy or configured WS base. */
export function experimentWsUrl(experimentId: string, token: string): string {
  // Use explicitly configured WS base if available (e.g., ws://host:port from .env)
  if (WS_BASE) {
    const base = WS_BASE.replace(/\/$/, '')
    const proto = base.startsWith('wss:') || base.startsWith('https:') ? 'wss:' : 'ws:'
    return `${proto}//${new URL(base).host}${base.includes('/experiments/') ? '' : `/experiments/${experimentId}/ws`}?token=${encodeURIComponent(token)}`
  }
  const base = API_BASE.replace(/\/$/, '')
  if (base.startsWith('/')) {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${window.location.host}${base}/experiments/${experimentId}/ws?token=${encodeURIComponent(token)}`
  }
  const httpUrl = new URL(base)
  const proto = httpUrl.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${httpUrl.host}${httpUrl.pathname.replace(/\/$/, '')}/experiments/${experimentId}/ws?token=${encodeURIComponent(token)}`
}

export function absoluteWsBase(): string | null {
  if (!WS_BASE) return null
  return WS_BASE.replace(/\/$/, '')
}
