/**
 * Derived analysis of a planner response.
 *
 * Everything here is computed from the plan the planner actually returned —
 * stage timings, declared inputs/outputs and the edge list. No stage, duration
 * or metric is invented, and a value the planner did not supply stays `null`
 * rather than being defaulted into a confident-looking number.
 */
import type { PipelinePlan, PipelineStage } from './plannedGraph'

// ── Duration parsing ─────────────────────────────────────────────────────────

const DURATION_RE = /(\d+(?:\.\d+)?)\s*(ms|s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hour|hours)\b/i

/** `"~5min"` / `"30s"` / `"2 h"` -> minutes. `null` when unparseable. */
export function parseDurationMinutes(raw: string | undefined): number | null {
  if (!raw) return null
  const m = DURATION_RE.exec(raw)
  if (!m) return null
  const value = Number(m[1])
  if (!Number.isFinite(value)) return null
  const unit = m[2].toLowerCase()
  if (unit === 'ms') return value / 60_000
  if (unit.startsWith('s')) return value / 60
  if (unit.startsWith('h')) return value * 60
  return value // m / min / minute
}

/** `"~5min"` -> `"~5 min"`, or `"—"` when the planner gave nothing usable. */
export function formatMinutes(minutes: number | null): string {
  if (minutes === null || !Number.isFinite(minutes)) return '—'
  if (minutes < 1) return `${Math.max(1, Math.round(minutes * 60))}s`
  const rounded = Math.round(minutes * 10) / 10
  return `${rounded} min`
}

// ── Name normalisation ───────────────────────────────────────────────────────

/** Loosely match `"raw dataset"`, `"raw_dataset"` and `"raw-dataset"`. */
function normalize(name: string): string {
  return name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
}

// ── Analysis ─────────────────────────────────────────────────────────────────

export interface FlowGap {
  kind: 'unresolved_input' | 'unused_output'
  stageId: string
  item: string
}

export interface PlanAnalysis {
  /** Longest chain by summed duration — where the time actually goes. */
  criticalPath: string[]
  /** Sum of every stage's duration, ignoring parallelism. */
  serialMinutes: number | null
  /** Critical path length: the plan cannot finish faster than this. */
  criticalMinutes: number | null
  /** Serial time divided by the widest parallel rank — a best case. */
  parallelMinutes: number | null
  /** Most stages that can run at once. */
  maxParallel: number
  /** Branch points: stages feeding more than one downstream stage. */
  fanOut: Array<{ stageId: string; count: number }>
  gaps: FlowGap[]
  /** Distinct agents, with how many stages each owns. */
  agents: Array<{ name: string; stages: number }>
  /** Stages whose duration the planner did not quantify. */
  unquantified: string[]
  /** Signals behind the planner's complexity label, explained rather than asserted. */
  complexitySignals: string[]
}

/** Edge shape the planner returns, normalized to `from`/`to`. */
type Link = { from: string; to: string }

function toLinks(plan: PipelinePlan): Link[] {
  return (plan.edges ?? []).map((e) => ({ from: e.from_stage, to: e.to_stage }))
}

/** Every stage reachable upstream of `id`, transitively. */
function ancestors(links: Link[], id: string): Set<string> {
  const acc = new Set<string>()
  const queue = [id]
  while (queue.length > 0) {
    const cur = queue.shift()!
    for (const l of links) {
      if (l.to === cur && !acc.has(l.from)) {
        acc.add(l.from)
        queue.push(l.from)
      }
    }
  }
  return acc
}

/** Every stage reachable downstream of `id`, transitively. */
function descendants(links: Link[], id: string): Set<string> {
  const acc = new Set<string>()
  const queue = [id]
  while (queue.length > 0)    {
    const cur = queue.shift()!
    for (const l of links) {
      if (l.from === cur && !acc.has(l.to)) {
        acc.add(l.to)
        queue.push(l.to)
      }
    }
  }
  return acc
}

function rankStages(stages: PipelineStage[], links: Link[]): Map<string, number> {
  const ids = stages.map((s) => s.id)
  const rank = new Map<string, number>(ids.map((id) => [id, 0]))
  for (let pass = 0; pass < ids.length + 1; pass += 1) {
    let changed = false
    for (const e of links) {
      if (!rank.has(e.from) || !rank.has(e.to)) continue
      const need = rank.get(e.from)! + 1
      if (need > rank.get(e.to)!) {
        rank.set(e.to, need)
        changed = true
      }
    }
    if (!changed) break
  }
  return rank
}

export function analyzePlan(plan: PipelinePlan): PlanAnalysis {
  const stages = plan.stages ?? []
  const links = toLinks(plan)
  const byId = new Map(stages.map((s) => [s.id, s]))
  const rank = rankStages(stages, links)

  // ── Durations ──────────────────────────────────────────────────────────────
  const minutes = new Map<string, number | null>()
  const unquantified: string[] = []
  stages.forEach((s) => {
    const m = parseDurationMinutes(s.estimated_duration)
    minutes.set(s.id, m)
    if (m === null) unquantified.push(s.id)
  })

  const known = stages.filter((s) => minutes.get(s.id) !== null)
  const serialMinutes = known.length
    ? known.reduce((sum, s) => sum + (minutes.get(s.id) as number), 0)
    : null

  // ── Critical path (weighted longest chain) ─────────────────────────────────
  // Only meaningful when every stage on the chain is quantified; otherwise a
  // partial sum would understate the path and mislead.
  let criticalPath: string[] = []
  let criticalMinutes: number | null = null
  if (known.length === stages.length && stages.length > 0) {
    const best = new Map<string, { length: number; path: string[] }>()
    const order = [...stages].sort((a, b) => (rank.get(a.id) ?? 0) - (rank.get(b.id) ?? 0))
    for (const s of order) {
      const parents = links.filter((l) => l.to === s.id).map((l) => l.from)
      let bestPrev = { length: 0, path: [] as string[] }
      for (const p of parents) {
        const cand = best.get(p)
        if (cand && cand.length > bestPrev.length) bestPrev = cand
      }
      const path = [...bestPrev.path, s.id]
      best.set(s.id, { length: bestPrev.length + (minutes.get(s.id) as number), path })
    }
    let winner = { length: 0, path: [] as string[] }
    for (const cand of best.values()) {
      if (cand.length > winner.length) winner = cand
    }
    criticalPath = winner.path
    criticalMinutes = winner.length || null
  }

  // ── Parallelism ────────────────────────────────────────────────────────────
  // Stages sharing a rank run concurrently, so a rank costs its SLOWEST stage,
  // not the sum. Summing here would make a branched plan look slower than the
  // serial total, which is exactly backwards.
  const rankCost = new Map<number, number>()
  const rankCount = new Map<number, number>()
  stages.forEach((s) => {
    const r = rank.get(s.id) ?? 0
    const cost = minutes.get(s.id) ?? 0
    rankCost.set(r, Math.max(rankCost.get(r) ?? 0, cost))
    rankCount.set(r, (rankCount.get(r) ?? 0) + 1)
  })
  const maxParallel = rankCount.size === 0 ? 0 : Math.max(...rankCount.values())
  const parallelMinutes = rankCost.size === 0 ? null : [...rankCost.values()].reduce((a, b) => a + b, 0)

  // ── Fan-out ────────────────────────────────────────────────────────────────
  const fanOutMap = new Map<string, number>()
  for (const l of links) {
    if (!byId.has(l.from) || !byId.has(l.to)) continue
    fanOutMap.set(l.from, (fanOutMap.get(l.from) ?? 0) + 1)
  }
  const fanOut = [...fanOutMap.entries()]
    .filter(([, count]) => count > 1)
    .map(([stageId, count]) => ({ stageId, count }))
    .sort((a, b) => b.count - a.count)

  // ── Data-flow gaps ────────────────────────────────────────────────────────
  const gaps: FlowGap[] = []
  for (const s of stages) {
    // Resolution is transitive: a stage may consume an artifact produced by any
    // ancestor, not only its immediate parent. Comparing against direct parents
    // would flag `raw_dataset` in preprocessing even though ingestion produces it.
    const ups = ancestors(links, s.id)
    // Entry stages legitimately take external inputs (a dataset, a prompt).
    if (ups.size > 0) {
      const produced = new Set(
        [...ups].flatMap((id) => (byId.get(id)?.outputs ?? []).map(normalize)).filter(Boolean),
      )
      for (const input of s.inputs ?? []) {
        const key = normalize(input)
        if (key && !produced.has(key)) {
          gaps.push({ kind: 'unresolved_input', stageId: s.id, item: input })
        }
      }
    }
    // Terminal stages legitimately produce outputs nothing consumes.
    const downs = descendants(links, s.id)
    if (downs.size > 0) {
      const consumed = new Set(
        [...downs].flatMap((id) => (byId.get(id)?.inputs ?? []).map(normalize)).filter(Boolean),
      )
      for (const output of s.outputs ?? []) {
        const key = normalize(output)
        if (key && !consumed.has(key)) {
          gaps.push({ kind: 'unused_output', stageId: s.id, item: output })
        }
      }
    }
  }

  // ── Agent roster ───────────────────────────────────────────────────────────
  const agentCounts = new Map<string, number>()
  for (const s of stages) {
    const name = s.agent?.trim()
    if (!name) continue
    agentCounts.set(name, (agentCounts.get(name) ?? 0) + 1)
  }
  const agents = [...agentCounts.entries()]
    .map(([name, count]) => ({ name, stages: count }))
    .sort((a, b) => b.stages - a.stages || a.name.localeCompare(b.name))

  // ── Complexity signals ─────────────────────────────────────────────────────
  // These explain *why* the label reads as it does, computed from the plan.
  const optionalCount = stages.filter((s) => s.optional).length
  const complexitySignals: string[] = [
    `${stages.length} stages`,
    `${links.length} connections`,
  ]
  if (fanOut.length > 0) {
    complexitySignals.push(`${fanOut.length} branching stage${fanOut.length === 1 ? '' : 's'}`)
  }
  if (optionalCount > 0) {
    complexitySignals.push(`${optionalCount} optional stage${optionalCount === 1 ? '' : 's'}`)
  }
  if (gaps.length > 0) {
    complexitySignals.push(`${gaps.length} unlinked data item${gaps.length === 1 ? '' : 's'}`)
  }

  return {
    criticalPath,
    serialMinutes,
    criticalMinutes,
    parallelMinutes,
    maxParallel,
    fanOut,
    gaps,
    agents,
    unquantified,
    complexitySignals,
  }
}

// ── Reachability (for focus/trace in the graph) ──────────────────────────────

/** The stage plus everything upstream and downstream of it. */
export function traceFrom(
  plan: PipelinePlan,
  stageId: string,
): { upstream: Set<string>; downstream: Set<string> } {
  const links = toLinks(plan)
  return { upstream: ancestors(links, stageId), downstream: descendants(links, stageId) }
}

// ── Export formats ───────────────────────────────────────────────────────────

/** Clipboard-ready Markdown checklist of the plan. */
export function planToMarkdown(plan: PipelinePlan): string {
  const lines: string[] = []
  lines.push(`# Pipeline plan — ${plan.task_type} (${plan.target_metric})`)
  lines.push('')
  lines.push(`**Complexity:** ${plan.complexity}  `)
  lines.push(`**Stages:** ${plan.stages.length} · **Connections:** ${plan.edges.length}  `)
  lines.push(`**Source:** ${plan.source}`)
  if (plan.summary) {
    lines.push('')
    lines.push(plan.summary)
  }
  lines.push('')
  lines.push('## Stages')
  plan.stages.forEach((s, i) => {
    lines.push(`${i + 1}. **${s.name}**${s.optional ? ' _(optional)_' : ''} — \`${s.agent}\``)
    lines.push(`   - Role: ${s.role}`)
    lines.push(`   - ${s.description}`)
    if (s.inputs?.length) lines.push(`   - Inputs: ${s.inputs.join(', ')}`)
    if (s.outputs?.length) lines.push(`   - Outputs: ${s.outputs.join(', ')}`)
    lines.push(`   - Est. duration: ${s.estimated_duration}`)
  })
  if (plan.assumptions?.length) {
    lines.push('')
    lines.push('## Assumptions')
    plan.assumptions.forEach((a) => lines.push(`- ${a}`))
  }
  if (plan.risks?.length) {
    lines.push('')
    lines.push('## Risks')
    plan.risks.forEach((r) => lines.push(`- ${r}`))
  }
  return lines.join('\n')
}

/** Mermaid flowchart — renders in GitHub, docs and most Markdown viewers. */
export function planToMermaid(plan: PipelinePlan): string {
  const id = (raw: string) => raw.replace(/[^A-Za-z0-9_]/g, '_') || 'stage'
  const lines: string[] = ['flowchart LR']
  for (const s of plan.stages) {
    const shape = s.optional ? ['{{', '}}'] : ['[', ']']
    const label = `${s.name}<br/><small>${s.agent}</small>`.replace(/"/g, "'")
    lines.push(`  ${id(s.id)}${shape[0]}"${label}"${shape[1]}`)
  }
  for (const e of plan.edges) {
    if (!plan.stages.some((s) => s.id === e.from_stage)) continue
    if (!plan.stages.some((s) => s.id === e.to_stage)) continue
    const arrow = e.label ? `-->|${e.label}|` : '-->'
    lines.push(`  ${id(e.from_stage)} ${arrow} ${id(e.to_stage)}`)
  }
  return lines.join('\n')
}