/**
 * AutoSage pipeline-graph derivation.
 *
 * Every node, edge and status is derived from backend payloads:
 *   - `GET  /objective-verification/objectives` — the objective graph itself
 *     (four objectives, their checks, and their order),
 *   - `GET  /objective-verification/stages`     — the ordered stage ids,
 *   - `POST /objective-verification/verify`      — real per-check verdicts,
 *   - the experiment record, for the problem statement and live run status.
 *
 * Nothing is fabricated. With no server definitions the graph is empty rather
 * than falling back to a client-side copy that could drift from the backend.
 */
import type {
  Dict,
  ObjectiveCheckDefinition,
  ObjectiveCheckResult,
  ObjectiveCheckStatus,
  ObjectiveDefinition,
  ObjectiveResult,
  ObjectiveStageStatus,
  ObjectiveStageUpdate,
  ObjectiveVerificationReport,
} from '../lib/api'
import type { Experiment, LogLine } from '../lib/types'

// ── Types ────────────────────────────────────────────────────────────────────

/** The four states the graph renders. */
export type PipelineStatus = 'pending' | 'running' | 'completed' | 'failed'

export type PipelineNodeKind = 'input' | 'objective' | 'report'

export type PipelineNodeData = {
  // React Flow requires node data to be index-signature compatible.
  [key: string]: unknown
  kind: PipelineNodeKind
  title: string
  subtitle: string
  status: PipelineStatus
  detail: string | null
  meta: string | null
  /** Server stage id this node renders. */
  stage: string
  /** Objective definition, for objective nodes. */
  objective: ObjectiveDefinition | null
  /** Objective verdict, when a report exists. */
  result: ObjectiveResult | null
  /** Check definitions, with results merged in when available. */
  checks: Array<{ definition: ObjectiveCheckDefinition; result: ObjectiveCheckResult | null }>
  confidence: number | null
  /** ML experiment lifecycle, shown separately from the node's own status. */
  runStatus?: string | null
  order: number
}

export interface PipelineGraphNode {
  id: string
  kind: PipelineNodeKind
  position: { x: number; y: number }
  data: PipelineNodeData
}

export interface PipelineGraphEdge {
  id: string
  source: string
  target: string
}

export interface PipelineGraphModel {
  nodes: PipelineGraphNode[]
  edges: PipelineGraphEdge[]
}

// ── Layout constants ─────────────────────────────────────────────────────────

const COL_W = 360
const ROW_H = 148

// ── Status mapping ────────────────────────────────────────────────────────────

/**
 * `PASS` / `FAIL` / `NOT_VERIFIED` / `BLOCKED` -> graph status.
 *
 * NOT_VERIFIED and BLOCKED both stay pending: neither is a success, and
 * neither is a failure. Only a real FAIL is drawn as failed.
 */
export function checkStatusToGraph(status: ObjectiveCheckStatus | undefined): PipelineStatus {
  if (status === 'PASS') return 'completed'
  if (status === 'FAIL') return 'failed'
  return 'pending'
}

/**
 * `PENDING` / `RUNNING` / `PASSED` / `FAILED` / `NOT_VERIFIED` / `BLOCKED`
 * -> graph status. NOT_VERIFIED and BLOCKED stay pending.
 */
export function stageStatusToGraph(status: ObjectiveStageStatus | undefined): PipelineStatus {
  switch (status) {
    case 'RUNNING':
      return 'running'
    case 'PASSED':
      return 'completed'
    case 'FAILED':
      return 'failed'
    default:
      return 'pending'
  }
}

/**
 * NOTE: there is deliberately no `experimentStatus -> PipelineStatus` mapper.
 * The ML experiment lifecycle (RUNNING/FAILED/CANCELLED) belongs to a
 * different workflow than the objective-verification graph, so it is never
 * used to colour a node here. It rides along as `runStatus` instead.
 */

// ── Helpers ──────────────────────────────────────────────────────────────────

function shortText(text: string | null | undefined, max = 240): string | null {
  if (!text) return null
  const trimmed = text.trim()
  if (!trimmed) return null
  return trimmed.length > max ? `${trimmed.slice(0, max - 1)}…` : trimmed
}

function nodeId(stage: string): string {
  return `stage:${stage}`
}

/** Latest update seen for a stage, which wins over the report verdict. */
function latestUpdateFor(
  updates: Map<string, ObjectiveStageUpdate>,
  stage: string,
): ObjectiveStageUpdate | undefined {
  return updates.get(stage)
}

// ── Node construction ────────────────────────────────────────────────────────

function buildChecks(
  definition: ObjectiveDefinition,
  result: ObjectiveResult | undefined,
): PipelineNodeData['checks'] {
  const byId = new Map((result?.checks ?? []).map((c) => [c.check_id, c]))
  return definition.checks.map((definitionCheck) => ({
    definition: definitionCheck,
    result: byId.get(definitionCheck.id) ?? null,
  }))
}

function checkSummary(checks: PipelineNodeData['checks']): string | null {
  const pass = checks.filter((c) => c.result?.status === 'PASS').length
  const fail = checks.filter((c) => c.result?.status === 'FAIL').length
  const unknown = checks.length - pass - fail
  const parts = [`${pass}/${checks.length} pass`]
  if (fail > 0) parts.push(`${fail} fail`)
  if (unknown > 0) parts.push(`${unknown} unverified`)
  return parts.join(' · ')
}

function inputNode(
  stage: string,
  experiment: Experiment | null,
  report: ObjectiveVerificationReport | null,
  update: ObjectiveStageUpdate | undefined,
): PipelineNodeData {
  // The report's echo of the problem wins: it is what verification actually
  // inspected, which may be an override the user supplied.
  const statement = report?.problem_statement || experiment?.prompt || experiment?.description || ''

  // A problem statement cannot fail. Its status answers one question only:
  // has a problem been captured for verification? A live `discovery` stage
  // update supersedes that when the backend is actually working.
  //
  // The ML experiment's own lifecycle (RUNNING/FAILED/CANCELLED) is a
  // *different* workflow's status and is deliberately NOT used here — a failed
  // training run does not make the user's problem statement invalid. It is
  // surfaced separately as `runStatus`.
  const status: PipelineStatus = update
    ? stageStatusToGraph(update.status)
    : statement
      ? 'completed'
      : 'pending'

  return {
    kind: 'input',
    title: 'User Problem Input',
    subtitle: report?.dataset_name || experiment?.name || 'session',
    status,
    detail: shortText(statement, 280),
    meta: experiment?.dataset ?? null,
    stage,
    objective: null,
    result: null,
    checks: [],
    confidence: null,
    runStatus: experiment?.status ?? null,
    order: 0,
  }
}

function objectiveNode(
  stage: string,
  definition: ObjectiveDefinition,
  result: ObjectiveResult | undefined,
  update: ObjectiveStageUpdate | undefined,
  order: number,
): PipelineNodeData {
  const checks = buildChecks(definition, result)
  // A live stage update is more current than the final report; fall back to the
  // objective's aggregate verdict, then to nothing at all.
  // An objective's status is a stage status, so it goes through the stage
  // mapper. A live update is more current than the final report.
  const status: PipelineStatus = update
    ? stageStatusToGraph(update.status)
    : result
      ? stageStatusToGraph(result.status)
      : 'pending'

  const detail =
    update?.message && status === 'running'
      ? update.message
      : (result?.statement ?? definition.statement)

  return {
    kind: 'objective',
    title: definition.title,
    subtitle: `Objective ${definition.number}`,
    status,
    detail: shortText(detail),
    meta: result ? checkSummary(checks) : `${definition.checks.length} checks`,
    stage,
    objective: definition,
    result: result ?? null,
    checks,
    confidence: result?.confidence ?? null,
    order,
  }
}

function reportNode(
  stage: string,
  report: ObjectiveVerificationReport | null,
  update: ObjectiveStageUpdate | undefined,
): PipelineNodeData {
  const objectives = report?.objectives ?? []
  const pass = objectives.filter((o) => o.status === 'PASSED').length
  const summary = objectives.length > 0 ? `${pass}/${objectives.length} objectives verified` : null

  const status: PipelineStatus = update
    ? stageStatusToGraph(update.status)
    : report
      ? stageStatusToGraph(report.overall_status)
      : 'pending'

  return {
    kind: 'report',
    title: 'Final Verification',
    subtitle: 'objective report',
    status,
    detail: shortText(update?.message || null, 200),
    meta: summary,
    stage,
    objective: null,
    result: null,
    checks: [],
    confidence: report?.overall_confidence ?? null,
    order: 0,
  }
}

// ── Layout ───────────────────────────────────────────────────────────────────

/**
 * Longest-path ranking: a node sits one column right of its deepest
 * predecessor. Bounded relaxation, so a malformed cycle degrades to a stable
 * layout instead of hanging.
 */
function assignRanks(ids: string[], edges: PipelineGraphEdge[]): Map<string, number> {
  const rank = new Map<string, number>(ids.map((id) => [id, 0]))
  for (let pass = 0; pass < ids.length + 1; pass += 1) {
    let changed = false
    for (const e of edges) {
      const need = (rank.get(e.source) ?? 0) + 1
      if (need > (rank.get(e.target) ?? 0)) {
        rank.set(e.target, need)
        changed = true
      }
    }
    if (!changed) break
  }
  return rank
}

function layout(
  nodes: Array<Omit<PipelineGraphNode, 'position'>>,
  edges: PipelineGraphEdge[],
): PipelineGraphNode[] {
  const rank = assignRanks(nodes.map((n) => n.id), edges)
  const columns = new Map<number, typeof nodes>()
  nodes.forEach((n) => {
    const r = rank.get(n.id) ?? 0
    const col = columns.get(r) ?? []
    col.push(n)
    columns.set(r, col)
  })

  const positioned: PipelineGraphNode[] = []
  columns.forEach((col, r) => {
    col.sort((a, b) => a.data.order - b.data.order)
    col.forEach((n, i) => {
      positioned.push({
        id: n.id,
        kind: n.kind,
        data: n.data,
        position: { x: r * COL_W, y: (i - (col.length - 1) / 2) * ROW_H },
      })
    })
  })
  return positioned
}

// ── Build ────────────────────────────────────────────────────────────────────

export interface BuildPipelineGraphInput {
  objectives: ObjectiveDefinition[]
  stages: string[]
  report: ObjectiveVerificationReport | null
  updates: ObjectiveStageUpdate[]
  experiment: Experiment | null
}

const FALLBACK_STAGES = ['discovery', 'objective_1', 'objective_2', 'objective_3', 'objective_4', 'report']

/**
 * Build the graph.
 *
 * Topology follows the server's stage list: problem input -> the four
 * objectives -> the final report. When the server sends no stage list we fall
 * back to the conventional discovery/objective_N/report ordering so the graph
 * still renders; objective *identity* never comes from a fallback, only from
 * the `/objectives` definitions.
 */
export function buildPipelineGraph({
  objectives,
  stages,
  report,
  updates,
  experiment,
}: BuildPipelineGraphInput): PipelineGraphModel {
  if (objectives.length === 0) return { nodes: [], edges: [] }

  const ordered = stages.length > 0 ? stages : FALLBACK_STAGES
  const byId = new Map(objectives.map((o) => [o.id, o]))
  const resultById = new Map((report?.objectives ?? []).map((o) => [o.id, o]))
  const updateByStage = new Map<string, ObjectiveStageUpdate>()
  updates.forEach((u) => updateByStage.set(u.stage, u))

  const draft: Array<Omit<PipelineGraphNode, 'position'>> = []
  const edges: PipelineGraphEdge[] = []

  // Server stage order is preserved verbatim — no stage is ever dropped or
  // reordered. Objectives the server defined but omitted from its stage list
  // are spliced in just before `report`, so the report stays terminal.
  const unlisted = objectives.filter((o) => !ordered.includes(o.id))
  const sequence: Array<{ stage: string }> = []
  ordered.forEach((stage) => {
    if (stage === 'report') {
      unlisted.forEach((definition) => sequence.push({ stage: definition.id }))
    }
    sequence.push({ stage })
  })

  let previous: string | null = null

  sequence.forEach(({ stage }) => {
    const id = nodeId(stage)
    const definition = byId.get(stage)

    let data: PipelineNodeData
    if (definition) {
      data = objectiveNode(
        stage,
        definition,
        resultById.get(definition.id),
        latestUpdateFor(updateByStage, stage),
        definition.number,
      )
    } else if (stage === 'discovery') {
      data = inputNode(stage, experiment, report, latestUpdateFor(updateByStage, stage))
    } else if (stage === 'report') {
      data = reportNode(stage, report, latestUpdateFor(updateByStage, stage))
    } else {
      // A stage the server declared that we have no renderer for. Show it
      // rather than silently dropping a node the backend considers real.
      const update = latestUpdateFor(updateByStage, stage)
      data = {
        kind: 'report',
        title: stage,
        subtitle: stage,
        status: stageStatusToGraph(update?.status),
        detail: update?.message ?? null,
        meta: null,
        stage,
        objective: null,
        result: null,
        checks: [],
        confidence: null,
        order: 0,
      }
    }

    draft.push({ id, kind: data.kind, data })
    if (previous) edges.push({ id: `${previous}->${id}`, source: previous, target: id })
    previous = id
  })

  return { nodes: layout(draft, edges), edges }
}

/** Aggregate counts for the header strip. */
export function graphSummary(model: PipelineGraphModel): Record<PipelineStatus, number> {
  const acc: Record<PipelineStatus, number> = { pending: 0, running: 0, completed: 0, failed: 0 }
  model.nodes.forEach((n) => {
    acc[n.data.status] += 1
  })
  return acc
}

/** Flat log lines for a node, matched on its stage id or objective title. */
export function logsForNode(logs: LogLine[], node: PipelineGraphNode): LogLine[] {
  if (logs.length === 0) return []
  const tokens = [node.data.stage, node.data.title, node.data.objective?.id].filter(
    (t): t is string => typeof t === 'string' && t.length > 0,
  )
  const needle = node.data.stage.replace(/^stage:/, '')
  const matched = logs.filter((l) => {
    const hay = `${l.agent} ${l.text}`.toLowerCase()
    return tokens.some((t) => hay.includes(t.toLowerCase())) || hay.includes(needle)
  })
  return matched.length > 0 ? matched : logs
}

/** Check-level roll-up for the header strip. */
export function checkTotals(
  model: PipelineGraphModel,
): Record<ObjectiveCheckStatus, number> {
  const acc: Record<ObjectiveCheckStatus, number> = {
    PASS: 0,
    FAIL: 0,
    NOT_VERIFIED: 0,
    BLOCKED: 0,
  }
  model.nodes.forEach((n) => {
    n.data.checks.forEach((c) => {
      // A check with no result yet is counted as NOT_VERIFIED, never PASS:
      // an unrendered check is an unevaluated check.
      acc[c.result?.status ?? 'NOT_VERIFIED'] += 1
    })
  })
  return acc
}

/** Session config echoed by the backend for traceability. */
export function reportDiscovery(report: ObjectiveVerificationReport | null): Dict {
  return report?.config ?? {}
}