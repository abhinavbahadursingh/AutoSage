import { useState } from 'react'
import { RotateCcw, Square } from 'lucide-react'
import { useStore } from '../store/context'
import { Badge } from '../components/ui/Badge'
import { statusTone } from '../lib/tones'
import { ExecutionTimeline } from '../components/workspace/ExecutionTimeline'
import { AgentDrawer } from '../components/workspace/AgentDrawer'
import { STAGE_META, formatApiDate } from '../data/experiments'
import { fmtMs } from '../lib/format'

const ACTIVE = new Set(['QUEUED', 'RUNNING', 'RETRYING'])

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span
        className="text-[11.5px] tracking-[0.1em] font-medium uppercase"
        style={{ color: 'var(--as-text-3)' }}
      >
        {label}
      </span>
      <span
        className="mono truncate text-[14.5px] font-medium"
        style={{ color: 'var(--as-text)' }}
        title={value}
      >
        {value}
      </span>
    </div>
  )
}

function ControlButton({
  children,
  onClick,
  primary = false,
  danger = false,
  disabled = false,
}: {
  children: React.ReactNode
  onClick: () => void
  primary?: boolean
  danger?: boolean
  disabled?: boolean
}) {
  const style: React.CSSProperties = primary
    ? {
        background: 'var(--as-accent)',
        borderColor: 'var(--as-accent)',
        color: '#fff',
      }
    : danger
      ? {
          background: 'color-mix(in oklch, var(--as-error) 8%, transparent)',
          borderColor: 'color-mix(in oklch, var(--as-error) 30%, transparent)',
          color: 'var(--as-error)',
        }
      : {
          background: 'var(--as-glass-bg)',
          borderColor: 'var(--as-border)',
          color: 'var(--as-text-2)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
        }

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex h-[34px] items-center gap-1.5 rounded-xl border px-4 text-[13.5px] font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50 hover:-translate-y-0.5 active:translate-y-0"
      style={{
        ...style,
        ...(primary
          ? { boxShadow: '0 4px 16px var(--as-accent-glow)' }
          : {}),
      }}
    >
      {children}
    </button>
  )
}

export function WorkspacePage() {
  const {
    activeExperiment,
    selectedNodeId,
    setSelectedNodeId,
    run,
    stop,
    busy,
    runState,
    elapsedLabel,
    experimentsLoading,
    authError,
    refreshExperiments,
  } = useStore()
  const [drawerOpen, setDrawerOpen] = useState(false)

  const exp = activeExperiment
  const isLive = exp ? ACTIVE.has(exp.status) && runState.id === exp.id : false
  const selectedNode = exp?.nodes.find((n) => n.id === selectedNodeId) ?? null

  if (!exp) {
    return (
      <div className="relative h-full overflow-y-auto" style={{ color: 'var(--as-text)' }}>
        <div className="mx-auto max-w-[640px] px-8 pt-16">
          <div
            className="glass grain rounded-3xl px-7 py-10 text-center"
            style={{ boxShadow: 'var(--as-glass-shadow)' }}
          >
            <p className="text-[18px] font-medium" style={{ color: 'var(--as-text)' }}>
              {experimentsLoading ? 'Loading experiments…' : authError ? 'Backend auth failed' : 'No experiment open'}
            </p>
            <p className="mt-2 text-[15px] leading-relaxed" style={{ color: 'var(--as-text-3)' }}>
              {authError
                ? authError
                : experimentsLoading
                  ? 'Fetching GET /api/v1/experiments'
                  : 'Create a new experiment or open one from the Experiments list.'}
            </p>
            {!experimentsLoading && (
              <button
                onClick={() => void refreshExperiments()}
                className="mt-5 h-[34px] rounded-xl border px-4 text-[14px] font-medium transition-all hover:-translate-y-0.5"
                style={{
                  background: 'var(--as-glass-bg)',
                  borderColor: 'var(--as-border)',
                  color: 'var(--as-text-2)',
                  backdropFilter: 'blur(12px)',
                }}
              >
                Refresh
              </button>
            )}
          </div>
        </div>
      </div>
    )
  }

  const activityNode =
    exp.nodes.find((n) => n.state === 'active') ??
    exp.nodes.find((n) => n.state === 'failed') ??
    (exp.status === 'COMPLETED'
      ? exp.nodes[exp.nodes.length - 1]
      : isLive
        ? (exp.nodes.find((n) => n.state === 'queued') ?? exp.nodes[0])
        : null)

  const metrics =
    exp.metrics.length > 0
      ? exp.metrics.slice(0, 3).map((m) => ({
          label: m.name.replace(/_/g, ' '),
          value: Math.abs(m.value) <= 1.5 && m.value !== 0 ? m.value.toFixed(3) : String(m.value),
        }))
      : [
          { label: 'Primary metric', value: '—' },
          { label: 'Model', value: '—' },
          { label: 'Status', value: exp.status },
        ]

  const openNode = (id: string) => {
    setSelectedNodeId(id)
    setDrawerOpen(true)
  }

  const doneCount = exp.nodes.filter((n) => n.state === 'done').length

  return (
    <div className="relative h-full overflow-y-auto" style={{ color: 'var(--as-text)' }}>
      <div className="mx-auto flex min-h-full w-full flex-col px-6 pt-8 pb-7 sm:px-8">

        {/* ── Header ── */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <h1
                className="max-w-[46ch] text-[24px] leading-tight font-semibold tracking-tight"
                style={{ color: 'var(--as-text)' }}
              >
                {exp.name}
              </h1>
              <Badge tone={statusTone(exp.status)}>
                {isLive && (
                  <span
                    className="mr-0.5 h-1 w-1 rounded-full animate-pulse inline-block"
                    style={{ background: 'var(--as-accent)' }}
                  />
                )}
                {exp.status}
              </Badge>
              <Badge tone={statusTone(exp.verificationStatus)}>{exp.verificationStatus}</Badge>
            </div>
            <p
              className="mono mt-2 max-w-[54ch] truncate text-[13px]"
              style={{ color: 'var(--as-text-3)' }}
              title={exp.prompt}
            >
              {exp.id} · {exp.prompt}
            </p>
            {exp.errorDetail && (
              <p
                className="mt-2 max-w-[70ch] rounded-2xl border px-4 py-2 text-[13.5px]"
                style={{
                  background: 'color-mix(in oklch, var(--as-error) 8%, transparent)',
                  borderColor: 'color-mix(in oklch, var(--as-error) 30%, transparent)',
                  color: 'var(--as-error)',
                }}
              >
                {exp.errorDetail}
              </p>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {ACTIVE.has(exp.status) ? (
              <ControlButton danger onClick={() => void stop(exp.id)} disabled={busy}>
                <Square size={11} /> Cancel
              </ControlButton>
            ) : (
              <ControlButton primary onClick={() => void run(exp.id)} disabled={busy}>
                <RotateCcw size={12} />
                {busy ? 'Starting…' : exp.status === 'COMPLETED' ? 'Re-run' : 'Run experiment'}
              </ControlButton>
            )}
          </div>
        </div>

        {/* ── Meta row ── */}
        <div
          className="mt-5 flex flex-wrap items-center gap-x-7 gap-y-2 border-y py-3"
          style={{ borderColor: 'var(--as-border)' }}
        >
          <MetaItem label="Dataset" value={exp.dataset} />
          <MetaItem label="Model" value={exp.model} />
          <MetaItem label="Runtime" value={isLive ? elapsedLabel : exp.runtime} />
          <MetaItem label="Metric" value={exp.metric} />
          <MetaItem label="Target" value={exp.target} />
          <MetaItem label="Created" value={formatApiDate(exp.createdAt)} />
        </div>

        {/* ── Execution timeline ── */}
        <section className="mt-8">
          <div className="mb-4 flex items-center justify-between">
            <span className="label-xs">Execution</span>
            <span className="mono text-[12.5px]" style={{ color: 'var(--as-text-3)' }}>
              {doneCount}/{exp.nodes.length} stages
              {isLive ? ' · running' : exp.status === 'FAILED' ? ' · failed' : exp.status === 'CANCELLED' ? ' · cancelled' : ''}
            </span>
          </div>
          <ExecutionTimeline experiment={exp} selectedId={selectedNodeId} onSelect={openNode} />
        </section>

        {/* ── Glass metric cards ── */}
        <section className="mt-8 grid grid-cols-3 gap-4">
          {metrics.map((m) => (
            <div
              key={m.label}
              className="glass grain rounded-2xl px-6 py-5 transition-all hover:-translate-y-0.5"
              style={{ boxShadow: 'var(--as-glass-shadow)' }}
            >
              <div
                className="text-[11.5px] tracking-[0.12em] font-semibold uppercase mb-2"
                style={{ color: 'var(--as-text-3)' }}
              >
                {m.label}
              </div>
              <div
                className="mono tnum text-[34px] leading-none font-semibold"
                style={{
                  color: 'var(--as-text)',
                  background: 'linear-gradient(135deg, var(--as-accent-hi), var(--as-teal-hi))',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: m.value !== '—' ? 'transparent' : 'var(--as-text-3)',
                  backgroundClip: 'text',
                }}
              >
                {m.value}
              </div>
            </div>
          ))}
        </section>

        {/* ── Current activity ── */}
        <section className="mt-8 flex min-h-0 flex-1 flex-col">
          <div className="mb-3 flex items-center justify-between">
            <span className="label-xs">Current activity</span>
            <span className="mono text-[12.5px]" style={{ color: 'var(--as-text-3)' }}>
              {activityNode
                ? `stage ${STAGE_META.find((m) => m.id === activityNode.stage)?.label.toLowerCase() ?? activityNode.stage}`
                : 'idle'}
            </span>
          </div>

          <div
            className="glass grain flex min-h-[160px] flex-1 flex-col rounded-2xl px-6 py-5"
            style={{ boxShadow: 'var(--as-glass-shadow)' }}
          >
            {!activityNode ? (
              <div className="my-auto py-3">
                <p className="text-[16px] font-medium" style={{ color: 'var(--as-text-2)' }}>
                  No active run
                </p>
                <p className="mt-1.5 max-w-[62ch] text-[15px] leading-relaxed" style={{ color: 'var(--as-text-3)' }}>
                  Start the experiment to watch agents work through the task graph. Each stage records its decision,
                  evidence and verification result.
                </p>
              </div>
            ) : (
              <div className="flex flex-1 items-center">
                <div className="flex w-full items-start gap-4">
                  <span
                    className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                    style={{
                      background:
                        activityNode.state === 'active'
                          ? 'var(--as-accent)'
                          : activityNode.state === 'failed'
                            ? 'var(--as-error)'
                            : 'var(--as-verify)',
                      boxShadow:
                        activityNode.state === 'active'
                          ? '0 0 10px var(--as-accent-glow)'
                          : activityNode.state === 'failed'
                            ? '0 0 10px rgba(239,68,68,0.4)'
                            : '0 0 10px rgba(16,185,129,0.4)',
                      animation: activityNode.state === 'active' ? 'node-pulse 1.8s ease-in-out infinite' : undefined,
                    }}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span className="text-[16px] font-semibold" style={{ color: 'var(--as-text)' }}>
                        {activityNode.agent}
                      </span>
                      <span className="mono text-[13px]" style={{ color: 'var(--as-text-3)' }}>
                        {activityNode.elapsedMs
                          ? fmtMs(activityNode.elapsedMs)
                          : isLive
                            ? 'running'
                            : exp.status.toLowerCase()}
                      </span>
                      <Badge tone={statusTone(activityNode.verification.status)}>
                        {activityNode.verification.status}
                      </Badge>
                    </div>
                    <p className="mt-2 max-w-[80ch] text-[15.5px] leading-relaxed" style={{ color: 'var(--as-text-2)' }}>
                      {activityNode.state === 'idle' ? activityNode.idleAction : activityNode.action}
                    </p>
                    <p className="mt-2 max-w-[80ch] text-[14.5px] leading-relaxed" style={{ color: 'var(--as-text-3)' }}>
                      {activityNode.decision}
                    </p>
                    <button
                      onClick={() => openNode(activityNode.id)}
                      className="mt-3 flex items-center gap-1.5 text-[14px] font-medium transition-colors hover:opacity-80"
                      style={{ color: 'var(--as-accent-hi)' }}
                    >
                      Inspect this agent →
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* ── Completed run result ── */}
        {exp.status === 'COMPLETED' && (
          <section className="mt-8">
            <div className="mb-4 flex items-center justify-between">
              <span className="label-xs">Run result</span>
              <span className="mono text-[12.5px]" style={{ color: 'var(--as-text-3)' }}>
                {exp.verificationStatus}
              </span>
            </div>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="glass grain rounded-2xl px-6 py-5" style={{ boxShadow: 'var(--as-glass-shadow)' }}>
                <div className="mb-2 text-[11.5px] font-semibold uppercase" style={{ color: 'var(--as-text-3)' }}>Final model</div>
                <p className="text-[16px] font-medium" style={{ color: 'var(--as-text)' }}>{exp.model}</p>
                <p className="mono mt-1 text-[13px]" style={{ color: 'var(--as-text-3)' }}>
                  primary metric: {exp.metrics[0] ? `${exp.metrics[0].name} = ${exp.metrics[0].value}` : exp.metric}
                </p>
                {typeof exp.resultSummary.model_spec === 'object' && exp.resultSummary.model_spec !== null && (
                  <p className="mt-2 text-[13.5px] leading-relaxed" style={{ color: 'var(--as-text-3)' }}>
                    {String((exp.resultSummary.model_spec as Record<string, unknown>).rationale ?? '') || `family ${exp.model}`}
                  </p>
                )}
              </div>

              <div className="glass grain rounded-2xl px-6 py-5" style={{ boxShadow: 'var(--as-glass-shadow)' }}>
                <div className="mb-2 text-[11.5px] font-semibold uppercase" style={{ color: 'var(--as-text-3)' }}>Pipeline / preprocessing</div>
                {(() => {
                  const spec = exp.resultSummary.preprocessing_spec as Record<string, unknown> | undefined
                  if (!spec || typeof spec !== 'object') {
                    return <p className="text-[14px]" style={{ color: 'var(--as-text-3)' }}>No preprocessing spec persisted.</p>
                  }
                  const rows: Array<[string, unknown]> = [
                    ['Imputation', spec.imputation],
                    ['Encoding', spec.encoding],
                    ['Scaling', spec.scaling],
                    ['Outliers', spec.outlier_handling],
                    ['Features', Array.isArray(spec.feature_engineering) ? spec.feature_engineering.join(', ') : spec.feature_engineering],
                    ['Dropped', Array.isArray(spec.drop_columns) ? spec.drop_columns.join(', ') : spec.drop_columns],
                  ]
                  return (
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-[13.5px]">
                      {rows.filter(([, v]) => v !== undefined && v !== null && v !== '' && v !== '[]').map(([k, v]) => (
                        <div className="flex justify-between gap-2" key={k}>
                          <dt style={{ color: 'var(--as-text-3)' }}>{k}</dt>
                          <dd className="mono" style={{ color: 'var(--as-text)' }}>{String(v)}</dd>
                        </div>
                      ))}
                      {typeof spec.rationale === 'string' && spec.rationale && (
                        <p className="col-span-2 mt-1 text-[13.5px]" style={{ color: 'var(--as-text-3)' }}>{spec.rationale}</p>
                      )}
                    </dl>
                  )
                })()}
              </div>

              <div className="glass grain rounded-2xl px-6 py-5" style={{ boxShadow: 'var(--as-glass-shadow)' }}>
                <div className="mb-2 text-[11.5px] font-semibold uppercase" style={{ color: 'var(--as-text-3)' }}>Verification</div>
                {(() => {
                  const v = exp.resultSummary.verification as Record<string, unknown> | undefined
                  if (!v || typeof v !== 'object') {
                    return <p className="text-[14px]" style={{ color: 'var(--as-text-3)' }}>No verification payload persisted.</p>
                  }
                  return (
                    <>
                      <p className="text-[14px] leading-relaxed" style={{ color: 'var(--as-text-2)' }}>
                        {String(v.summary ?? (v.passed ? 'Verification passed.' : 'Verification did not pass.'))}
                      </p>
                      {Array.isArray(v.checks) && v.checks.length > 0 && (
                        <ul className="mono mt-2 list-disc pl-5 text-[13px]" style={{ color: 'var(--as-text-3)' }}>
                          {v.checks.map((c, i) => (
                            <li key={i}>{String(c)}</li>
                          ))}
                        </ul>
                      )}
                      {Array.isArray(v.failures) && v.failures.length > 0 && (
                        <ul className="mono mt-2 list-disc pl-5 text-[13px]" style={{ color: 'var(--as-error)' }}>
                          {v.failures.map((c, i) => (
                            <li key={i}>{String(c)}</li>
                          ))}
                        </ul>
                      )}
                    </>
                  )
                })()}
              </div>

              <div className="glass grain rounded-2xl px-6 py-5" style={{ boxShadow: 'var(--as-glass-shadow)' }}>
                <div className="mb-2 text-[11.5px] font-semibold uppercase" style={{ color: 'var(--as-text-3)' }}>Stage outputs</div>
                <ul className="space-y-1.5 text-[13.5px]">
                  {exp.nodes
                    .filter((n) => n.state === 'done' && n.decision && n.decision !== 'Completed under backend lifecycle.')
                    .map((n) => (
                      <li key={n.id}>
                        <span className="mono" style={{ color: 'var(--as-text-3)' }}>{n.stage}</span>
                        <span style={{ color: 'var(--as-text-2)' }}> — {n.decision}</span>
                      </li>
                    ))}
                </ul>
              </div>

              <div className="glass grain rounded-2xl px-6 py-5 lg:col-span-2" style={{ boxShadow: 'var(--as-glass-shadow)' }}>
                <div className="mb-2 text-[11.5px] font-semibold uppercase" style={{ color: 'var(--as-text-3)' }}>Event trail</div>
                <ul className="mono space-y-1 text-[13px] leading-relaxed" style={{ color: 'var(--as-text-3)' }}>
                  {Array.isArray(exp.resultSummary.events) && exp.resultSummary.events.length > 0 ? (
                    (exp.resultSummary.events as unknown[]).slice(-14).map((e, i) => (
                      <li key={i}>· {String(e)}</li>
                    ))
                  ) : (
                    <li>No events persisted.</li>
                  )}
                </ul>
              </div>
            </div>
          </section>
        )}

<p className="mt-6 max-w-[92ch] text-[13.5px] leading-relaxed" style={{ color: 'var(--as-text-3)' }}>
          Click any point in the execution timeline to open its full record — reasoning, evidence, tool calls,
          verification proofs and analysis appear only when you ask for them.
        </p>
      </div>

      {drawerOpen && selectedNode && (
        <AgentDrawer experiment={exp} node={selectedNode} onClose={() => setDrawerOpen(false)} />
      )}
    </div>
  )
}
