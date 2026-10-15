/**
 * Planned-pipeline graph derivation.
 *
 * Builds a DAG from the planner's response (`POST /pipeline/plan`): the
 * stages it returned and the edges between them. Nothing is invented — the
 * planner is the sole source of node identity, ordering and connectivity.
 */

// ── Planner response shape ───────────────────────────────────────────────────

export interface PipelineStage {
  id: string
  name: string
  agent: string
  role: string
  description: string
  inputs: string[]
  outputs: string[]
  estimated_duration: string
  optional: boolean
}

export interface PipelineEdge {
  from_stage: string
  to_stage: string
  label: string
}

export interface PipelinePlan {
  task_type: string
  target_metric: string
  complexity: string
  stages: PipelineStage[]
  edges: PipelineEdge[]
  summary: string
  assumptions: string[]
  risks: string[]
  source: string
}

export interface PlannedGraphNodeData {
  // React Flow requires node data to be index-signature compatible.
  [key: string]: unknown
  stage: PipelineStage
  order: number
}

export interface PlannedGraphNode {
  id: string
  position: { x: number; y: number }
  data: PlannedGraphNodeData
}

export interface PlannedGraphEdge {
  id: string
  source: string
  target: string
  label: string
}

export interface PlannedGraphModel {
  nodes: PlannedGraphNode[]
  edges: PlannedGraphEdge[]
}

const COL_W = 300
const ROW_H = 150

/**
 * Longest-path ranking: a node sits one column right of its deepest
 * predecessor. Bounded relaxation so a malformed cycle degrades to a stable
 * layout instead of hanging.
 */
function assignRanks(ids: string[], edges: PlannedGraphEdge[]): Map<string, number> {
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

/** Place ranked nodes on a grid: columns left-to-right, rows centred per column. */
function layout(
  nodes: Array<{ id: string; data: PlannedGraphNodeData }>,
  edges: PlannedGraphEdge[],
): PlannedGraphNode[] {
  const rank = assignRanks(nodes.map((n) => n.id), edges)
  const columns = new Map<number, typeof nodes>()
  nodes.forEach((n) => {
    const r = rank.get(n.id) ?? 0
    const col = columns.get(r) ?? []
    col.push(n)
    columns.set(r, col)
  })

  const positioned: PlannedGraphNode[] = []
  columns.forEach((col, r) => {
    col.sort((a, b) => a.data.order - b.data.order)
    col.forEach((n, i) => {
      positioned.push({
        id: n.id,
        data: n.data,
        position: { x: r * COL_W, y: (i - (col.length - 1) / 2) * ROW_H },
      })
    })
  })
  return positioned
}

/** Build the graph for a planner response. */
export function buildPlannedGraph(plan: PipelinePlan): PlannedGraphModel {
  const stages = plan.stages ?? []
  const edges: PlannedGraphEdge[] = (plan.edges ?? []).map((e) => ({
    id: `${e.from_stage}->${e.to_stage}`,
    source: e.from_stage,
    target: e.to_stage,
    label: e.label ?? '',
  }))

  const nodes = stages.map((stage, i) => ({
    id: stage.id,
    data: { stage, order: i },
  }))

  return { nodes: layout(nodes, edges), edges }
}

/** Stage ids with no incoming edge — the entry points of the plan. */
export function planRoots(model: PlannedGraphModel): Set<string> {
  const targeted = new Set(model.edges.map((e) => e.target))
  return new Set(model.nodes.map((n) => n.id).filter((id) => !targeted.has(id)))
}