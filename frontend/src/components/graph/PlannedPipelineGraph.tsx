import { useCallback, useMemo, useState, type KeyboardEvent } from 'react'
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  type NodeProps,
  useReactFlow,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { AlertTriangle, Bot, Clock, GitBranch, Search, X } from 'lucide-react'
import { Badge } from '../ui/Badge'
import {
  buildPlannedGraph,
  planRoots,
  type PipelinePlan,
  type PlannedGraphNodeData,
} from '../../data/plannedGraph'
import { analyzePlan, traceFrom } from '../../data/planAnalysis'

type PlannedNode = Node<PlannedGraphNodeData, 'planned'>

// ── Node card ────────────────────────────────────────────────────────────────

function PlannedNodeCard({ data, selected }: NodeProps<PlannedNode>) {
  const { stage, order, dimmed, matched } = data
  return (
    <div
      className={[
        'glass relative w-[250px] rounded-2xl px-4 py-3 transition-all duration-200',
        selected ? 'shadow-[0_0_0_1.5px_var(--as-accent),0_12px_40px_rgba(0,0,0,0.5)]' : '',
        dimmed ? 'opacity-30' : '',
        matched ? 'shadow-[0_0_0_1.5px_var(--as-teal),0_8px_30px_rgba(45,212,191,0.25)]' : '',
      ].join(' ')}
      style={{ borderColor: selected ? 'var(--as-accent)' : 'var(--as-glass-border)' }}
    >
      <Handle type="target" position={Position.Left} className="!opacity-0" />

      <span
        aria-hidden
        className="absolute top-3 bottom-3 left-0 w-[3px] rounded-r-full"
        style={{ background: stage.optional ? 'var(--as-text-3)' : 'var(--as-accent)' }}
      />

      {stage.optional && (
        <span className="absolute -right-1.5 -top-1.5">
          <Badge tone="dim">optional</Badge>
        </span>
      )}

      <div className="pl-1.5">
        <div className="flex items-center gap-2">
          <span
            className="mono flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[10px]"
            style={{
              background: selected ? 'var(--as-accent-glow)' : 'var(--as-glass-bg-2)',
              color: selected ? 'var(--as-accent-hi)' : 'var(--as-text-3)',
            }}
          >
            {order + 1}
          </span>
          <Bot size={13} className="shrink-0 text-[var(--as-text-3)]" aria-hidden />
          <span className="min-w-0 flex-1 truncate text-[13.5px] font-semibold text-[var(--as-text)]">
            {stage.name}
          </span>
        </div>

        <div className="mono mt-0.5 truncate text-[10.5px] text-[var(--as-text-3)]">
          {stage.agent} · {stage.role}
        </div>

        <p className="mt-1.5 line-clamp-3 text-[11.5px] leading-snug text-[var(--as-text-2)]">
          {stage.description}
        </p>

        {/* Real data-flow tokens declared by the planner */}
        {(stage.outputs?.length > 0 || stage.inputs?.length > 0) && (
          <div className="mt-2 flex flex-wrap gap-1">
            {stage.outputs?.slice(0, 3).map((o) => (
              <span
                key={`o-${o}`}
                className="mono rounded bg-[var(--as-teal-lo)] px-1 py-[1px] text-[9.5px]"
                style={{ color: 'var(--as-teal-hi)' }}
                title={`output: ${o}`}
              >
                {o}
              </span>
            ))}
            {stage.inputs?.slice(0, 3).map((i) => (
              <span
                key={`i-${i}`}
                className="mono rounded bg-[var(--as-glass-bg-2)] px-1 py-[1px] text-[9.5px] text-[var(--as-text-3)]"
                title={`input: ${i}`}
              >
                {i}
              </span>
            ))}
            {(stage.outputs?.length ?? 0) + (stage.inputs?.length ?? 0) > 6 && (
              <span className="mono text-[9.5px] text-[var(--as-text-3)]">
                +{((stage.outputs?.length ?? 0) + (stage.inputs?.length ?? 0)) - 6}
              </span>
            )}
          </div>
        )}

        <div className="mono mt-2 flex items-center gap-1 border-t border-[var(--as-border)] pt-1.5 text-[10px] text-[var(--as-text-3)]">
          <Clock size={9} aria-hidden />
          {stage.estimated_duration}
        </div>
      </div>

      <Handle type="source" position={Position.Right} className="!opacity-0" />
    </div>
  )
}

const nodeTypes = { planned: PlannedNodeCard }

// ── Graph ────────────────────────────────────────────────────────────────────

/**
 * The prepared flow graph for a planner response.
 *
 * Every node and edge comes from `POST /pipeline/plan`; this component only
 * lays it out and makes it navigable. It has no dependency on any experiment,
 * run, or verification state.
 */
/**
 * The prepared flow graph for a planner response.
 *
 * Every node and edge comes from `POST /pipeline/plan`; this component only
 * lays it out and makes it navigable. It has no dependency on any experiment,
 * run, or verification state.
 *
 * `useReactFlow` needs a provider above it, so this wrapper provides one and
 * delegates to the inner flow component.
 */
export function PlannedPipelineGraph(props: {
  plan: PipelinePlan
  selectedStage: string | null
  onSelectStage: (id: string | null) => void
}) {
  return (
    <ReactFlowProvider>
      <PlannedFlow {...props} />
    </ReactFlowProvider>
  )
}

function PlannedFlow({
  plan,
  selectedStage,
  onSelectStage,
}: {
  plan: PipelinePlan
  selectedStage: string | null
  onSelectStage: (id: string | null) => void
}) {
  const [query, setQuery] = useState('')
  const model = useMemo(() => buildPlannedGraph(plan), [plan])
  const roots = useMemo(() => planRoots(model), [model])
  const analysis = useMemo(() => analyzePlan(plan), [plan])
  const trace = useMemo(
    () => (selectedStage ? traceFrom(plan, selectedStage) : null),
    [plan, selectedStage],
  )
  const flow = useReactFlow()

  /** Case-insensitive match across the fields a user would search by. */
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return null
    const set = new Set<string>()
    for (const s of plan.stages ?? []) {
      const hay = `${s.name} ${s.agent} ${s.role} ${s.description} ${(s.inputs ?? []).join(' ')} ${(
        s.outputs ?? []
      ).join(' ')}`.toLowerCase()
      if (hay.includes(q)) set.add(s.id)
    }
    return set
  }, [query, plan.stages])

  const nodes = useMemo<PlannedNode[]>(
    () =>
      model.nodes.map((n) => ({
        id: n.id,
        type: 'planned' as const,
        position: n.position,
        data: {
          ...n.data,
          // Outside the selected stage's lineage everything recedes.
          dimmed: trace ? !trace.upstream.has(n.id) && !trace.downstream.has(n.id) && n.id !== selectedStage : false,
          matched: matches ? matches.has(n.id) : false,
        },
      })),
    [model.nodes, trace, matches, selectedStage],
  )

  const edges = useMemo<Edge[]>(
    () =>
      model.edges.map((e) => {
        const onPath = trace ? trace.upstream.has(e.source) || trace.downstream.has(e.source) : false
        const selected = selectedStage === e.source || selectedStage === e.target
        const dimmed = trace ? !onPath : false
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          type: 'smoothstep' as const,
          label: e.label || undefined,
          labelStyle: { fill: 'var(--as-text-3)', fontSize: 10 },
          labelBgStyle: { fill: 'var(--as-bg-2)' },
          animated: selected,
          style: {
            stroke: selected ? 'var(--as-accent-hi)' : 'var(--as-text-3)',
            strokeWidth: selected ? 2 : 1.5,
            opacity: dimmed ? 0.2 : 1,
          },
        }
      }),
    [model.edges, selectedStage, trace],
  )

  const handleNodeClick = useCallback(
    (_: unknown, node: PlannedNode) => onSelectStage(node.id),
    [onSelectStage],
  )

  /** Move selection to the previous/next stage in graph order. */
  const step = useCallback(
    (delta: number) => {
      const ids = model.nodes.map((n) => n.id)
      if (ids.length === 0) return
      const idx = selectedStage ? ids.indexOf(selectedStage) : -1
      const next = idx === -1 ? (delta > 0 ? 0 : ids.length - 1) : (idx + delta + ids.length) % ids.length
      onSelectStage(ids[next])
    },
    [model.nodes, selectedStage, onSelectStage],
  )

  /** Jump to the next stage that matches the current search. */
  const stepToMatch = useCallback(
    (delta: number) => {
      if (!matches || matches.size === 0) return
      const ids = model.nodes.map((n) => n.id).filter((id) => matches.has(id))
      const idx = selectedStage ? ids.indexOf(selectedStage) : -1
      const next = idx === -1 ? (delta > 0 ? 0 : ids.length - 1) : (idx + delta + ids.length) % ids.length
      onSelectStage(ids[next])
    },
    [matches, model.nodes, selectedStage, onSelectStage],
  )

  const onKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault()
        if (matches && matches.size > 0) stepToMatch(1)
        else step(1)
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault()
        if (matches && matches.size > 0) stepToMatch(-1)
        else step(-1)
      } else if (e.key === 'Enter' && matches && matches.size > 0) {
        e.preventDefault()
        stepToMatch(1)
      } else if (e.key === 'Escape') {
        onSelectStage(null)
      }
    },
    [step, stepToMatch, matches, onSelectStage],
  )

  const optionalCount = plan.stages.filter((s) => s.optional).length
  const gapCount = analysis.gaps.length

  return (
    <div className="glass overflow-hidden rounded-2xl">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--as-border)] px-4 py-2.5">
        <GitBranch size={13} className="text-violet-400" aria-hidden />
        <span className="text-[12.5px] font-semibold text-[var(--as-text)]">Prepared flow</span>

        {/* Search */}
        <div className="relative ml-2 min-w-[180px] flex-1 sm:max-w-[280px]">
          <Search
            size={12}
            className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-[var(--as-text-3)]"
            aria-hidden
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Find a stage, agent or artifact…"
            aria-label="Search stages"
            className="w-full rounded-lg border border-[var(--as-border)] bg-[var(--as-bg-2)] py-1.5 pr-7 pl-7 text-[12px] text-[var(--as-text)] outline-none placeholder:text-[var(--as-text-3)] focus:border-[var(--as-accent)]"
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              aria-label="Clear search"
              className="absolute top-1/2 right-2 -translate-y-1/2 text-[var(--as-text-3)] hover:text-[var(--as-text)]"
            >
              <X size={11} />
            </button>
          )}
        </div>

        {matches && (
          <span className="mono text-[11px] text-[var(--as-teal-hi)]">
            {matches.size} match{matches.size === 1 ? '' : 'es'}
          </span>
        )}

        <span className="mono ml-auto text-[11px] text-[var(--as-text-3)]">
          {model.nodes.length} stages · {model.edges.length} connections
          {optionalCount > 0 ? ` · ${optionalCount} optional` : ''}
        </span>

        <div className="flex items-center gap-1">
          <button
            onClick={() => step(-1)}
            aria-label="Previous stage"
            className="rounded-md border border-[var(--as-border)] px-1.5 py-1 text-[11px] text-[var(--as-text-2)] transition hover:bg-[var(--as-glass-bg-2)] hover:text-[var(--as-text)]"
          >
            ‹
          </button>
          <button
            onClick={() => step(1)}
            aria-label="Next stage"
            className="rounded-md border border-[var(--as-border)] px-1.5 py-1 text-[11px] text-[var(--as-text-2)] transition hover:bg-[var(--as-glass-bg-2)] hover:text-[var(--as-text)]"
          >
            ›
          </button>
          <button
            onClick={() => void flow.fitView({ padding: 0.16, duration: 400 })}
            aria-label="Fit graph to view"
            className="rounded-md border border-[var(--as-border)] px-1.5 py-1 text-[11px] text-[var(--as-text-2)] transition hover:bg-[var(--as-glass-bg-2)] hover:text-[var(--as-text)]"
          >
            Fit
          </button>
          {selectedStage && (
            <button
              onClick={() => onSelectStage(null)}
              aria-label="Clear selection"
              className="rounded-md border border-[var(--as-border)] px-1.5 py-1 text-[11px] text-[var(--as-text-2)] transition hover:bg-[var(--as-glass-bg-2)] hover:text-[var(--as-text)]"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Canvas */}
      <div
        className="relative h-[540px]"
        tabIndex={0}
        role="application"
        aria-label="Pipeline flow graph. Use arrow keys to move between stages."
        onKeyDown={onKeyDown}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={handleNodeClick}
          onPaneClick={() => onSelectStage(null)}
          fitView
          fitViewOptions={{ padding: 0.16 }}
          minZoom={0.25}
          maxZoom={1.8}
          nodesDraggable={false}
          nodesConnectable={false}
          colorMode="dark"
          className="[&_.react-flow__controls-button]:!border-[var(--as-border)] [&_.react-flow__controls-button]:!bg-[var(--as-bg-3)] [&_.react-flow__controls-button]:!fill-[var(--as-text-2)] [&_.react-flow__controls-button:hover]:!fill-[var(--as-accent-hi)] [&_.react-flow__minimap]:!border-[var(--as-border)] [&_.react-flow__minimap]:!bg-[var(--as-bg-3)]"
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={22}
            size={1}
            color="var(--as-text-3)"
            style={{ opacity: 0.35 }}
          />
          <Controls showInteractive={false} position="bottom-right" />
          <MiniMap
            pannable
            zoomable
            position="top-right"
            nodeColor={(n) =>
              (n.data as PlannedGraphNodeData).stage.optional
                ? 'var(--as-text-3)'
                : 'var(--as-accent)'
            }
            maskColor="color-mix(in oklch, var(--as-bg) 72%, transparent)"
          />
        </ReactFlow>

        {model.nodes.length === 0 && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <p className="text-[13px] text-[var(--as-text-3)]">This plan returned no stages.</p>
          </div>
        )}

        {selectedStage && trace && (
          <div className="pointer-events-none absolute top-3 left-3 rounded-lg border border-[var(--as-border)] bg-[var(--as-bg-2)]/90 px-2.5 py-1.5 text-[11px] text-[var(--as-text-2)] backdrop-blur">
            Tracing <span className="text-[var(--as-accent-hi)]">{selectedStage}</span> ·{' '}
            {trace.upstream.size} upstream · {trace.downstream.size} downstream
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-[var(--as-border)] px-4 py-2.5 text-[11px] text-[var(--as-text-3)]">
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-[3px] rounded bg-[var(--as-accent)]" /> required stage
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-[3px] rounded bg-[var(--as-text-3)]" /> optional
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-px w-5 bg-[var(--as-text-3)]" /> data flow
        </span>
        <span className="flex items-center gap-1.5">
          <span className="rounded bg-[var(--as-teal-lo)] px-1 py-[1px] text-[9.5px]" style={{ color: 'var(--as-teal-hi)' }}>
            artifact
          </span>
          produced
        </span>
        <span className="flex items-center gap-1.5">
          <AlertTriangle size={11} className="text-[var(--as-warn)]" aria-hidden />
          {roots.size} entry point{roots.size === 1 ? '' : 's'}
          {gapCount > 0 ? ` · ${gapCount} unlinked` : ''}
        </span>
        <span className="ml-auto hidden sm:inline">↑↓←→ step · Enter next match · Esc clear</span>
      </div>
    </div>
  )
}