import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Loader2,
  Play,
  RefreshCw,
  Terminal,
  XCircle,
} from 'lucide-react'
import {
  api,
  type ObjectiveDefinition,
  type ObjectiveStageUpdate,
  type ObjectiveVerificationReport,
} from '../../lib/api'
import type { Experiment } from '../../lib/types'
import {
  buildPipelineGraph,
  checkTotals,
  graphSummary,
  logsForNode,
  type PipelineNodeData,
  type PipelineStatus,
} from '../../data/pipelineGraph'

type PipelineNode = Node<PipelineNodeData, 'pipeline'>

// ── Status presentation ──────────────────────────────────────────────────────

const STATUS_META: Record<PipelineStatus, { label: string; color: string }> = {
  pending: { label: 'pending', color: 'var(--as-text-3)' },
  running: { label: 'running', color: 'var(--as-accent-hi)' },
  completed: { label: 'completed', color: 'var(--as-verify)' },
  failed: { label: 'failed', color: 'var(--as-error)' },
}

function StatusIcon({ status, size = 12 }: { status: PipelineStatus; size?: number }) {
  if (status === 'running') return <Loader2 size={size} className="animate-spin" aria-hidden />
  if (status === 'completed') return <CheckCircle2 size={size} aria-hidden />
  if (status === 'failed') return <XCircle size={size} aria-hidden />
  return <CircleDashed size={size} aria-hidden />
}

const CHECK_COLOR: Record<string, string> = {
  PASS: 'var(--as-verify)',
  FAIL: 'var(--as-error)',
  UNVERIFIED: 'var(--as-text-3)',
}

const KIND_ACCENT: Record<PipelineNodeData['kind'], string> = {
  input: 'var(--as-teal)',
  objective: 'var(--as-accent)',
  report: 'var(--as-verify)',
}

// ── Custom node ──────────────────────────────────────────────────────────────

function PipelineNodeCard({ data, selected }: NodeProps<PipelineNode>) {
  const meta = STATUS_META[data.status]
  const accent = KIND_ACCENT[data.kind]
  const running = data.status === 'running'

  // Per-check pips: a compact read of the objective's real verdicts.
  const pips = data.checks.map((c) => c.result?.status ?? 'UNVERIFIED')

  return (
    <div
      className={[
        'glass relative w-[280px] rounded-2xl px-4 py-3 transition-all duration-200',
        selected ? 'shadow-[0_0_0_1.5px_var(--as-accent),0_12px_40px_rgba(0,0,0,0.5)]' : '',
        running ? 'anim-node-pulse' : '',
      ].join(' ')}
      style={{ borderColor: selected ? 'var(--as-accent)' : 'var(--as-glass-border)' }}
    >
      <Handle type="target" position={Position.Left} className="!opacity-0" />

      <span
        aria-hidden
        className="absolute top-3 bottom-3 left-0 w-[3px] rounded-r-full"
        style={{ background: meta.color }}
      />

      <div className="flex items-start gap-2.5 pl-1.5">
        <span
          className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg"
          style={{ background: `color-mix(in oklch, ${accent} 18%, transparent)`, color: meta.color }}
        >
          <StatusIcon status={data.status} size={13} />
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <span className="min-w-0 flex-1 text-[13.5px] font-semibold leading-tight text-[var(--as-text)]">
              {data.title}
            </span>
            <span
              className="mono mt-0.5 shrink-0 rounded px-1.5 py-[1px] text-[9px] tracking-[0.08em] uppercase"
              style={{ color: meta.color, background: `color-mix(in oklch, ${meta.color} 14%, transparent)` }}
            >
              {meta.label}
            </span>
          </div>

          <div className="mono mt-0.5 truncate text-[10.5px] text-[var(--as-text-3)]">
            {data.subtitle}
          </div>

          {data.detail && (
            <p className="mt-1.5 line-clamp-3 text-[11.5px] leading-snug text-[var(--as-text-2)]">
              {data.detail}
            </p>
          )}

          {pips.length > 0 && (
            <div className="mt-2 flex items-center gap-1">
              {pips.map((p, i) => (
                <span
                  key={i}
                  title={`${data.checks[i].definition.title}: ${p}`}
                  className="h-1.5 flex-1 rounded-full"
                  style={{ background: CHECK_COLOR[p] ?? 'var(--as-text-3)', opacity: 0.85 }}
                />
              ))}
            </div>
          )}

          {(data.meta || data.confidence !== null) && (
            <div className="mono mt-2 flex items-center justify-between gap-2 border-t border-[var(--as-border)] pt-1.5 text-[10px] text-[var(--as-text-3)]">
              <span className="truncate">{data.meta}</span>
              {data.confidence !== null && (
                <span className="shrink-0">conf {data.confidence.toFixed(2)}</span>
              )}
            </div>
          )}
        </div>
      </div>

      <Handle type="source" position={Position.Right} className="!opacity-0" />
    </div>
  )
}

const nodeTypes = { pipeline: PipelineNodeCard }

// ── Graph ────────────────────────────────────────────────────────────────────

export function AutoSagePipelineGraph({ experiment }: { experiment: Experiment | null }) {
  const [objectives, setObjectives] = useState<ObjectiveDefinition[]>([])
  const [stages, setStages] = useState<string[]>([])
  const [updates] = useState<ObjectiveStageUpdate[]>([])
  // Reports are tagged with the experiment they describe so switching runs can
  // never render another run's verdicts.
  const [reportRun] = useState<{
    experimentId: string
    report: ObjectiveVerificationReport | null
    error: string | null
  } | null>(null)
  const [verifying] = useState(false)
  const [definitionsFailed, setDefinitionsFailed] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const experimentId = experiment?.id ?? null

  // Graph definition comes from the server, once.
  useEffect(() => {
    let cancelled = false
    Promise.all([api.listObjectives(), api.objectiveStages()])
      .then(([defs, stageList]) => {
        if (cancelled) return
        setObjectives(defs)
        setStages(stageList.stages)
        setDefinitionsFailed(false)
      })
      .catch(() => {
        if (!cancelled) setDefinitionsFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Verification no longer runs against a pre-existing experiment: every run
  // is a fresh session created from a newly submitted problem and dataset on
  // the Objective Verification page. This graph is therefore read-only here —
  // it renders the fixed objective sequence, but never starts a run.
  const verify = useCallback(() => {
    window.location.assign('/objectives')
  }, [])

  const report = reportRun?.experimentId === experimentId ? reportRun.report : null
  const verifyError = reportRun?.experimentId === experimentId ? reportRun.error : null

  const model = useMemo(
    () => buildPipelineGraph({ objectives, stages, report, updates, experiment }),
    [objectives, stages, report, updates, experiment],
  )

  const counts = useMemo(() => graphSummary(model), [model])
  const checks = useMemo(() => checkTotals(model), [model])

  const nodes = useMemo<PipelineNode[]>(
    () =>
      model.nodes.map((n) => ({
        id: n.id,
        type: 'pipeline' as const,
        position: n.position,
        data: n.data,
      })),
    [model.nodes],
  )

  // Edges inherit real state: an edge into a running node animates, and an
  // edge touching a failed node reads as broken.
  const edges = useMemo<Edge[]>(() => {
    const byId = new Map(model.nodes.map((n) => [n.id, n.data.status]))
    return model.edges.map((e) => {
      const to = byId.get(e.target)
      const from = byId.get(e.source)
      const failed = from === 'failed' || to === 'failed'
      const color =
        failed ? 'var(--as-error)' : to === 'running' ? 'var(--as-accent-hi)' : 'var(--as-text-3)'
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        type: 'smoothstep' as const,
        animated: to === 'running',
        style: { stroke: color, strokeWidth: to === 'running' ? 2 : 1.5 },
      }
    })
  }, [model])

  const selected = useMemo(
    () => model.nodes.find((n) => n.id === selectedId) ?? null,
    [model.nodes, selectedId],
  )

  const visibleLogs = useMemo(
    () => (selected ? logsForNode(experiment?.logs ?? [], selected) : (experiment?.logs ?? [])),
    [selected, experiment?.logs],
  )

  // ── Empty / unavailable states ────────────────────────────────────────────

  if (!experiment) {
    return (
      <div className="glass flex h-full min-h-[420px] flex-col items-center justify-center gap-2 rounded-2xl p-8 text-center">
        <CircleDashed size={26} style={{ color: 'var(--as-text-3)' }} aria-hidden />
        <p className="text-[15px] font-medium text-[var(--as-text-2)]">No experiment selected</p>
        <p className="max-w-[46ch] text-[13px] text-[var(--as-text-3)]">
          Open or start an experiment to verify the four project objectives against it.
        </p>
      </div>
    )
  }

  if (definitionsFailed) {
    return (
      <div className="glass flex min-h-[240px] flex-col items-center justify-center gap-2 rounded-2xl p-8 text-center">
        <AlertTriangle size={24} style={{ color: 'var(--as-warn)' }} aria-hidden />
        <p className="text-[15px] font-medium text-[var(--as-text-2)]">
          Objective definitions unavailable
        </p>
        <p className="max-w-[52ch] text-[13px] text-[var(--as-text-3)]">
          The backend did not serve <span className="mono">/objective-verification/objectives</span>.
          The graph is not drawn from a client-side fallback, so it stays empty rather than
          showing checks the server has not defined.
        </p>
        <button onClick={() => window.location.reload()} className="btn-ghost mt-2 flex h-8 items-center gap-1.5 rounded-lg px-3 text-[12.5px]">
          <RefreshCw size={12} aria-hidden /> Retry
        </button>
      </div>
    )
  }

  // ── Main ──────────────────────────────────────────────────────────────────

  return (
    <div className="flex min-h-0 flex-col gap-3">
      {/* Status strip */}
      <div className="flex flex-wrap items-center gap-2">
        {(['completed', 'running', 'failed', 'pending'] as PipelineStatus[]).map((s) => (
          <span
            key={s}
            className="mono flex items-center gap-1.5 rounded-lg border px-2 py-1 text-[11px]"
            style={{
              color: STATUS_META[s].color,
              borderColor: `color-mix(in oklch, ${STATUS_META[s].color} 32%, transparent)`,
              background: `color-mix(in oklch, ${STATUS_META[s].color} 8%, transparent)`,
            }}
          >
            <StatusIcon status={s} size={11} />
            {counts[s]} {STATUS_META[s].label}
          </span>
        ))}

        <span className="mono ml-1 text-[11px] text-[var(--as-text-3)]">
          {model.nodes.length} nodes · {model.edges.length} edges
        </span>

        {report && (
          <span className="mono ml-1 flex items-center gap-1.5 text-[11px]" style={{ color: CHECK_COLOR[report.overall_status === 'PASSED' ? 'PASS' : report.overall_status === 'FAILED' ? 'FAIL' : 'NOT_VERIFIED'] }}>
            <StatusIcon
              status={
                report.overall_status === 'PASSED'
                  ? 'completed'
                  : report.overall_status === 'FAILED'
                    ? 'failed'
                    : 'pending'
              }
              size={11}
            />
            overall {report.overall_status.toLowerCase()}
          </span>
        )}

        <div className="ml-auto flex items-center gap-2">
          {report && (
            <span className="mono hidden text-[11px] text-[var(--as-text-3)] md:inline">
              {checks.PASS} pass · {checks.FAIL} fail · {checks.NOT_VERIFIED} not verified
            </span>
          )}
          <button
            onClick={() => void verify()}
            disabled={verifying}
            className="btn-primary flex h-7 items-center gap-1.5 rounded-lg px-3 text-[11.5px] disabled:opacity-60"
          >
            {verifying ? <Loader2 size={11} className="animate-spin" /> : report ? <RefreshCw size={11} /> : <Play size={11} />}
            {verifying ? 'Verifying…' : report ? 'Re-verify' : 'Verify objectives'}
          </button>
        </div>
      </div>

      {verifyError && (
        <p className="flex items-start gap-1.5 text-[11.5px] text-[var(--as-error)]">
          <AlertTriangle size={12} className="mt-[2px] shrink-0" aria-hidden />
          {verifyError}
        </p>
      )}

      <div className="flex min-h-0 flex-col gap-3">
        {/* Canvas */}
        <div className="glass relative h-[620px] shrink-0 overflow-hidden rounded-2xl">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodeClick={(_, n) => setSelectedId(n.id)}
            onPaneClick={() => setSelectedId(null)}
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
              nodeColor={(n) => STATUS_META[(n.data as PipelineNodeData).status].color}
              maskColor="color-mix(in oklch, var(--as-bg) 72%, transparent)"
            />
          </ReactFlow>

          {model.nodes.length === 0 && (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <p className="text-[13px] text-[var(--as-text-3)]">Loading objective graph…</p>
            </div>
          )}
        </div>

        {/* Inspector + execution log, side by side beneath the graph */}
        <div className="grid min-h-0 gap-3 lg:grid-cols-2">
          <div className="glass max-h-[420px] min-h-[320px] overflow-y-auto rounded-2xl p-4">
            <h3 className="label-xs mb-3">Node inspector</h3>
            {selected ? (
              <div key={selected.id} className="anim-fade-in">
                <div className="flex items-start gap-2">
                  <span className="min-w-0 flex-1 text-[15px] font-semibold text-[var(--as-text)]">
                    {selected.data.title}
                  </span>
                  <span
                    className="mono shrink-0 rounded px-1.5 py-[1px] text-[9.5px] uppercase"
                    style={{
                      color: STATUS_META[selected.data.status].color,
                      background: `color-mix(in oklch, ${STATUS_META[selected.data.status].color} 14%, transparent)`,
                    }}
                  >
                    {STATUS_META[selected.data.status].label}
                  </span>
                </div>
                <p className="mono mt-0.5 text-[11px] text-[var(--as-text-3)]">
                  {selected.data.subtitle} · {selected.data.stage}
                </p>

                {selected.data.detail && (
                  <p className="mt-2.5 text-[12.5px] leading-relaxed text-[var(--as-text-2)]">
                    {selected.data.detail}
                  </p>
                )}

                {/* ML run lifecycle — a different workflow's status, so it is
                    labelled explicitly and never drives the node badge. */}
                {selected.data.runStatus && (
                  <p className="mono mt-2 text-[11px] text-[var(--as-text-3)]">
                    experiment run:{' '}
                    <span
                      style={{
                        color:
                          selected.data.runStatus === 'COMPLETED'
                            ? 'var(--as-verify)'
                            : selected.data.runStatus === 'FAILED' ||
                                selected.data.runStatus === 'CANCELLED'
                              ? 'var(--as-error)'
                              : 'var(--as-accent-hi)',
                      }}
                    >
                      {selected.data.runStatus.toLowerCase()}
                    </span>
                  </p>
                )}

                {/* Per-check verdicts, definitions from the server */}
                {selected.data.checks.length > 0 && (
                  <div className="mt-3 space-y-2.5 border-t border-[var(--as-border)] pt-3">
                    <span className="label-xs">Checks</span>
                    {selected.data.checks.map((c) => {
                      const status = c.result?.status ?? 'UNVERIFIED'
                      return (
                        <div key={c.definition.id}>
                          <div className="flex items-center gap-1.5">
                            <StatusIcon
                              status={status === 'PASS' ? 'completed' : status === 'FAIL' ? 'failed' : 'pending'}
                              size={11}
                            />
                            <span className="min-w-0 flex-1 truncate text-[12px] text-[var(--as-text)]">
                              {c.definition.title}
                            </span>
                            <span
                              className="mono shrink-0 text-[10px]"
                              style={{ color: CHECK_COLOR[status] }}
                            >
                              {status.toLowerCase()}
                            </span>
                          </div>
                          <p className="mt-0.5 pl-4 text-[11px] leading-snug text-[var(--as-text-3)]">
                            {c.result?.reasoning || c.definition.description}
                          </p>
                          {c.result?.evidence?.length ? (
                            <ul className="mt-1 space-y-0.5 pl-4">
                              {c.result.evidence.map((ev, i) => (
                                <li key={i} className="mono text-[10px] leading-snug text-[var(--as-text-3)]">
                                  · {ev}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mono mt-0.5 pl-4 text-[10px] text-[var(--as-text-3)]">
                              source: {c.definition.evidence_source}
                            </p>
                          )}
                          {c.result?.artifact && (
                            <p className="mono mt-0.5 truncate pl-4 text-[10px] text-[var(--as-text-3)]">
                              {c.result.artifact}
                            </p>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}

                {report && selected.data.kind === 'report' && (
                  <div className="mt-3 border-t border-[var(--as-border)] pt-3">
                    <span className="label-xs">Objectives</span>
                    <ul className="mt-1.5 space-y-1">
                      {report.objectives.map((o) => (
                        <li key={o.id} className="flex items-center gap-1.5 text-[12px]">
                          <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: CHECK_COLOR[o.status] }} />
                          <span className="min-w-0 flex-1 truncate text-[var(--as-text-2)]">{o.title}</span>
                          <span className="mono shrink-0 text-[10px]" style={{ color: CHECK_COLOR[o.status] }}>
                            {o.status.toLowerCase()}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-[12.5px] text-[var(--as-text-3)]">
                Select a node to inspect its checks, evidence and execution logs.
              </p>
            )}
          </div>

          <div className="glass flex max-h-[420px] min-h-[320px] flex-col overflow-hidden rounded-2xl">
            <div className="flex shrink-0 items-center gap-2 border-b border-[var(--as-border)] px-4 py-2">
              <Terminal size={12} style={{ color: 'var(--as-text-3)' }} aria-hidden />
              <span className="label-xs">Execution log</span>
              <span className="mono ml-auto text-[10px] text-[var(--as-text-3)]">{visibleLogs.length}</span>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-2">
              {visibleLogs.length === 0 ? (
                <p className="py-2 text-[11.5px] text-[var(--as-text-3)]">No log lines yet.</p>
              ) : (
                visibleLogs.slice(-120).map((l) => (
                  <div key={l.id} className="anim-log-in flex gap-2 py-[3px] text-[11.5px]">
                    <span className="mono shrink-0 text-[var(--as-text-3)]">{l.ts}</span>
                    <span
                      className="mono shrink-0"
                      style={{
                        color:
                          l.level === 'VERIFY'
                            ? 'var(--as-verify)'
                            : l.level === 'WARN'
                              ? 'var(--as-warn)'
                              : l.level === 'DECISION'
                                ? 'var(--as-accent-hi)'
                                : l.level === 'METRIC'
                                  ? 'var(--as-teal)'
                                  : 'var(--as-text-2)',
                      }}
                    >
                      {l.level}
                    </span>
                    <span className="mono shrink-0 text-[var(--as-text-3)]">{l.agent}</span>
                    <span className="min-w-0 flex-1 break-words text-[var(--as-text-2)]">{l.text}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}