import type { ApiUser, ExperimentRead } from '../lib/api'
import type {
  AgentNode,
  Experiment,
  ExperimentStatus,
  LogLine,
  MetricPoint,
  NodeState,
  StageId,
  VerificationLevel,
  VerificationStatus,
} from '../lib/types'

/**
 * Stage graph aligned to backend LangGraph STAGE_ORDER
 * (orchestrator → discovery → profiler → preprocessor → model_selector
 *  → ml_experiment → verification), plus UI request/pipeline bookends
 * that map to experiment lifecycle events.
 */
export const STAGE_META: { id: StageId; label: string; short: string; agent: string; role: string }[] = [
  { id: 'request', label: 'User Request', short: 'REQ', agent: 'Orchestrator', role: 'planner · router' },
  { id: 'discovery', label: 'Dataset Discovery', short: 'DISC', agent: 'Data Scout', role: 'retrieval · registry' },
  { id: 'profiling', label: 'Profiling', short: 'PROF', agent: 'Profiler', role: 'statistics · schema' },
  { id: 'preprocessing', label: 'Preprocessing', short: 'PREP', agent: 'Preprocessor', role: 'cleaning · encoding' },
  { id: 'selection', label: 'Model Selection', short: 'SEL', agent: 'Model Selector', role: 'search · ranking' },
  { id: 'training', label: 'Training', short: 'TRAIN', agent: 'Trainer', role: 'fit · checkpoint' },
  { id: 'evaluation', label: 'Evaluation', short: 'EVAL', agent: 'Evaluator', role: 'metrics · slices' },
  { id: 'verification', label: 'Verification', short: 'VERIF', agent: 'Verifier', role: 'claims · evidence' },
  { id: 'pipeline', label: 'Final Pipeline', short: 'PIPE', agent: 'Orchestrator', role: 'freeze · export' },
]

// One row per agent name (Orchestrator owns both request + pipeline stages).
// Stages are looked up by name in Agents.tsx via agentStages(), so ids must be unique.
export const AGENT_ROSTER = STAGE_META.reduce<
  { id: string; name: string; role: string; state: 'idle'; stage: StageId; order: number }[]
>((acc, s, i) => {
  const id = s.agent.toLowerCase().replace(/\s+/g, '_')
  if (acc.some((a) => a.id === id)) return acc
  acc.push({ id, name: s.agent, role: s.role, state: 'idle', stage: s.id, order: i })
  return acc
}, [])

/** Backend agent_name / stage string → StageId */
const BACKEND_STAGE_MAP: Record<string, StageId> = {
  orchestrator: 'request',
  discovery: 'discovery',
  profiler: 'profiling',
  preprocessor: 'preprocessing',
  model_selector: 'selection',
  selection: 'selection',
  ml_experiment: 'training',
  training: 'training',
  evaluation: 'evaluation',
  verification: 'verification',
  ml_training: 'training',
  pipeline: 'pipeline',
  queued: 'request',
  request: 'request',
}

export function stageFromBackend(raw: string): StageId | null {
  const key = raw.trim().toLowerCase()
  if (key in BACKEND_STAGE_MAP) return BACKEND_STAGE_MAP[key]
  return null
}

const IDLE_TEXT: Record<StageId, { idle: string; active: string }> = {
  request: {
    idle: 'Awaiting a task description.',
    active: 'Parsing intent and compiling the task graph.',
  },
  discovery: {
    idle: 'Scanning dataset registry for candidate tables.',
    active: 'Locating dataset and verifying provenance.',
  },
  profiling: {
    idle: 'Profiling columns for type, drift and missingness.',
    active: 'Computing schema and target statistics.',
  },
  preprocessing: {
    idle: 'Assembling preprocessing graph.',
    active: 'Building imputation, encoding and leakage checks.',
  },
  selection: {
    idle: 'Ranking candidate learners for the task.',
    active: 'Searching model shortlist against the evaluation metric.',
  },
  training: {
    idle: 'Waiting for model selection.',
    active: 'Fitting candidate models in the sandbox.',
  },
  evaluation: {
    idle: 'Waiting for training metrics.',
    active: 'Scoring holdout metrics.',
  },
  verification: {
    idle: 'Verification engine standing by.',
    active: 'Recomputing claims and checking leakage gates.',
  },
  pipeline: {
    idle: 'Pipeline not frozen yet.',
    active: 'Freezing the verified pipeline.',
  },
}

function emptyNode(stage: StageId, state: NodeState = 'idle'): AgentNode {
  const meta = STAGE_META.find((m) => m.id === stage)!
  return {
    id: `n-${stage}`,
    stage,
    agent: meta.agent,
    role: meta.role,
    state,
    action: IDLE_TEXT[stage].active,
    idleAction: IDLE_TEXT[stage].idle,
    input: '—',
    decision: state === 'idle' ? '—' : 'Awaiting backend stage event.',
    confidence: null,
    evidence: [],
    verification: {
      status: 'UNVERIFIED',
      note: state === 'done' ? 'Stage completed (backend status).' : 'Not yet verified.',
    },
    tools: [],
  }
}

/** Flatten result_summary.ml_result metrics (backend sandbox metrics dict). */
export function metricsFromSummary(summary: Record<string, unknown>): MetricPoint[] {
  const ml = summary.ml_result
  if (!ml || typeof ml !== 'object') return []
  const rec = ml as Record<string, unknown>
  // Canonical shape from the workflow: {metric: "recall", value: 0.87, ...}
  if (typeof rec.metric === 'string' && typeof rec.value === 'number') {
    const pts: MetricPoint[] = [{ name: rec.metric, value: rec.value }]
    if (typeof rec.validation_strategy === 'string') {
      // keep the canonical point only — notes/strategy are metadata, not metrics
    }
    return pts
  }
  // Legacy/free-form numeric map
  const out: MetricPoint[] = []
  for (const [name, value] of Object.entries(rec)) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      out.push({ name, value })
    }
  }
  return out
}

function formatRuntime(raw: ExperimentRead): string {
  if (raw.started_at && raw.completed_at) {
    const ms = new Date(raw.completed_at).getTime() - new Date(raw.started_at).getTime()
    if (Number.isFinite(ms) && ms >= 0) {
      const totalSec = Math.max(1, Math.round(ms / 1000))
      const m = Math.floor(totalSec / 60)
      const s = totalSec % 60
      return m > 0 ? `${m}m ${String(s).padStart(2, '0')}s` : `${s}s`
    }
  }
  return '—'
}

function verificationFromStatus(status: ExperimentStatus): VerificationStatus {
  if (status === 'COMPLETED') return 'VERIFIED'
  if (status === 'FAILED') return 'QUARANTINED'
  if (status === 'CANCELLED') return 'UNVERIFIED'
  return 'UNVERIFIED'
}

/** Real per-stage output extracted from result_summary state slots. */
export function stageOutputSummary(stage: StageId, resultSummary: Record<string, unknown>): string | null {
  const s = resultSummary as Record<string, any>
  switch (stage) {
    case 'discovery': {
      const d = s.dataset_info
      if (d && typeof d === 'object') {
        const parts = [
          d.dataset_name && `dataset ${String(d.dataset_name)}`,
          typeof d.rows === 'number' && `${d.rows} rows`,
          Array.isArray(d.columns) && `${d.columns.length} cols`,
          d.task_hint && `task ${String(d.task_hint)}`,
        ].filter(Boolean)
        if (parts.length) return parts.join(' · ')
      }
      return null
    }
    case 'profiling': {
      const p = s.profile
      return p && typeof p === 'object' && typeof p.summary === 'string' && p.summary ? p.summary : null
    }
    case 'preprocessing': {
      const p = s.preprocessing_spec
      if (p && typeof p === 'object') {
        if (typeof p.rationale === 'string' && p.rationale) return p.rationale
        const bits = [
          p.imputation && `impute ${p.imputation}`,
          p.encoding && `encode ${p.encoding}`,
          p.scaling && `scale ${p.scaling}`,
        ].filter(Boolean)
        if (bits.length) return bits.join(' · ')
      }
      return null
    }
    case 'selection': {
      const m = s.model_spec
      if (m && typeof m === 'object') {
        if (typeof m.rationale === 'string' && m.rationale) return m.rationale
        if (typeof m.family === 'string' && m.family) return `family ${m.family}`
      }
      return null
    }
    case 'training': {
      const ml = s.ml_result
      if (ml && typeof ml === 'object') {
        const head =
          typeof ml.metric === 'string'
            ? `${ml.metric}=${typeof ml.value === 'number' ? ml.value : '—'}`
            : null
        const tail = [ml.validation_strategy, ml.notes].filter(
          (v): v is string => typeof v === 'string' && v.length > 0,
        )
        return [head, ...tail].filter(Boolean).join(' · ') || null
      }
      return null
    }
    case 'verification': {
      const v = s.verification
      if (v && typeof v === 'object') {
        if (typeof v.summary === 'string' && v.summary) return v.summary
        if (typeof v.passed === 'boolean') return `passed=${v.passed}`
      }
      return null
    }
    default:
      return null
  }
}

/**
 * Derive timeline node states from backend experiment status + stages_completed.
 * No fabricated decisions/confidence — unknown fields stay null/empty.
 */
export function deriveNodes(
  status: ExperimentStatus,
  resultSummary: Record<string, unknown>,
  liveStage: StageId | null = null,
): AgentNode[] {
  const stagesCompleted = Array.isArray(resultSummary.stages_completed)
    ? (resultSummary.stages_completed as unknown[]).map(String)
    : []

  const completedStages = new Set<StageId>()
  for (const s of stagesCompleted) {
    const mapped = stageFromBackend(s)
    if (mapped) completedStages.add(mapped)
  }

  return STAGE_META.map((meta) => {
    const node = emptyNode(meta.id)

    if (status === 'COMPLETED') {
      // Terminal success: mark every stage done (backend finished the run).
      const real = stageOutputSummary(meta.id, resultSummary)
      return {
        ...node,
        state: 'done' as NodeState,
        decision: real ?? 'Completed under backend lifecycle.',
        evidence: real ? [real] : [],
        verification: {
          status: 'VERIFIED',
          note: completedStages.size
            ? `Backend reported stages: ${[...completedStages].join(', ')}`
            : 'Experiment status COMPLETED.',
        },
      }
    }

    if (status === 'FAILED' || status === 'CANCELLED') {
      // Leave prior progress unknown except stages explicitly completed.
      if (completedStages.has(meta.id)) {
        return { ...node, state: 'done' as NodeState, decision: stageOutputSummary(meta.id, resultSummary) ?? node.decision }
      }
      return {
        ...node,
        state: status === 'FAILED' && meta.id === 'training' ? ('failed' as NodeState) : ('idle' as NodeState),
        decision:
          status === 'FAILED'
            ? 'Run failed before this stage reported success.'
            : 'Run cancelled.',
      }
    }

    if (status === 'CREATED') return node

    if (status === 'QUEUED' || status === 'RETRYING') {
      if (meta.id === 'request') {
        return { ...node, state: 'queued' as NodeState, decision: 'Queued on backend worker.' }
      }
      return node
    }

    if (status === 'RUNNING') {
      if (completedStages.has(meta.id)) {
        return { ...node, state: 'done' as NodeState, decision: stageOutputSummary(meta.id, resultSummary) ?? 'Passed before live stage.' }
      }
      if (liveStage) {
        if (meta.id === liveStage) {
          return { ...node, state: 'active' as NodeState }
        }
        const liveIdx = STAGE_META.findIndex((m) => m.id === liveStage)
        const myIdx = STAGE_META.findIndex((m) => m.id === meta.id)
        if (liveIdx >= 0 && myIdx >= 0 && myIdx < liveIdx) {
          return { ...node, state: 'done' as NodeState, decision: 'Passed before live stage.' }
        }
        if (liveIdx >= 0 && myIdx > liveIdx) {
          return { ...node, state: 'queued' as NodeState }
        }
      }
      // Running without a live stage event: request bookend active.
      if (meta.id === 'request') {
        return { ...node, state: 'active' as NodeState }
      }
      return { ...node, state: 'queued' as NodeState }
    }

    return node
  })
}

function str(v: unknown, fallback = ''): string {
  if (typeof v === 'string' && v) return v
  return fallback
}

export function mapExperiment(
  raw: ExperimentRead,
  owner: string,
  liveStage: StageId | null = null,
  extraLogs: LogLine[] = [],
): Experiment {
  const config = raw.config ?? {}
  const summary = raw.result_summary ?? {}

  const prompt = str(config.prompt, raw.description ?? '')
  const dataset = str(config.dataset_name) || str(config.dataset) || '—'
  const target = str(config.target_column, '—')
  const mlResult = (summary.ml_result ?? {}) as Record<string, unknown>
  const modelSpec = (summary.model_spec ?? {}) as Record<string, unknown>
  const metric =
    str(config.metric) || str(config.evaluation_metric) || str(mlResult.metric) || '—'
  const model =
    str(modelSpec.family) ||
    str(config.model_family) ||
    str(summary.model_family as string | undefined) ||
    '—'

  // Budget / verification level are not backend fields — keep UI stable with '—'
  // unless config carries known optional keys (it does not today).
  const verificationLevel: VerificationLevel = 'standard'

  const nodes = deriveNodes(raw.status, summary, liveStage)
  const metrics = metricsFromSummary(summary)

  return {
    id: raw.id,
    workspaceId: raw.workspace_id,
    name: raw.name,
    description: raw.description,
    prompt: prompt || raw.name,
    status: raw.status,
    dataset,
    target,
    metric,
    budget: '—',
    verificationLevel,
    model,
    runtime: formatRuntime(raw),
    verificationStatus: verificationFromStatus(raw.status),
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    startedAt: raw.started_at,
    completedAt: raw.completed_at,
    errorDetail: raw.error_detail,
    retryCount: raw.retry_count,
    maxRetries: raw.max_retries,
    owner,
    config,
    resultSummary: summary,
    metrics,
    nodes,
    logs: extraLogs,
    raw,
  }
}

export function userName(user: ApiUser | null): string {
  if (!user) return 'you'
  if (user.name) return user.name
  if (user.email) return user.email.split('@')[0] ?? 'you'
  return 'you'
}

export function formatApiDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    const p = (n: number) => String(n).padStart(2, '0')
    return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())} UTC`
  } catch {
    return iso
  }
}
