import { useEffect, useMemo, useState } from 'react'
import { X } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { statusTone } from '../../lib/tones'
import { fmtMs } from '../../lib/format'
import { STAGE_META, formatApiDate } from '../../data/experiments'
import type { AgentNode, Experiment } from '../../lib/types'

type Tab = 'reasoning' | 'evidence' | 'tools' | 'analysis'

const TABS: { id: Tab; label: string }[] = [
  { id: 'reasoning', label: 'Reasoning' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'tools', label: 'Tools & logs' },
  { id: 'analysis', label: 'Analysis' },
]

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-ink-700/80 px-5 py-4">
      <div className="label-xs mb-2">{label}</div>
      {children}
    </div>
  )
}

export function AgentDrawer({
  experiment,
  node,
  onClose,
}: {
  experiment: Experiment
  node: AgentNode | null
  onClose: () => void
}) {
  const [tabState, setTabState] = useState<{ id: string; tab: Tab }>({ id: '', tab: 'reasoning' })
  const tab: Tab = tabState.id === (node?.id ?? '') ? tabState.tab : 'reasoning'
  const setTab = (t: Tab) => setTabState({ id: node?.id ?? '', tab: t })

  const stageLogs = useMemo(
    () => (node ? experiment.logs.filter((l) => l.agent === node.agent).slice(-40) : []),
    [experiment.logs, node],
  )
  const metrics = experiment.metrics
  const maxMetric = metrics.length ? Math.max(...metrics.map((m) => Math.abs(m.value) || 0), 1e-9) : 1

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!node) return null
  const meta = STAGE_META.find((m) => m.id === node.stage)
  const stageIdx = experiment.nodes.findIndex((n) => n.id === node.id)

  return (
    <>
      <div className="anim-fade-in fixed inset-0 z-40 bg-ink-950/45" onClick={onClose} />
      <aside className="anim-slide-in-drawer fixed inset-y-0 right-0 z-50 flex w-[min(460px,100vw)] flex-col border-l border-ink-600 bg-ink-900 shadow-[-18px_0_48px_-24px_rgba(0,0,0,0.9)]">
        <header className="flex items-start justify-between gap-3 border-b border-ink-600 px-5 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2.5">
              <span className="mono text-[12.5px] tracking-[0.1em] text-paper-500">{`0${stageIdx + 1}`}</span>
              <h2 className="truncate text-[17px] font-semibold text-paper-50">{node.agent}</h2>
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                  node.state === 'active'
                    ? 'animate-pulse bg-accent-400'
                    : node.state === 'done'
                      ? 'bg-verify-500'
                      : node.state === 'failed'
                        ? 'bg-conflict-500'
                        : 'bg-ink-500'
                }`}
              />
            </div>
            <div className="mono mt-1 text-[13px] text-paper-500">
              {meta?.label} · stage {node.stage}
              {node.elapsedMs ? ` · ${fmtMs(node.elapsedMs)}` : node.state === 'active' ? ' · running' : ''}
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-sm p-1 text-paper-500 transition hover:bg-ink-750 hover:text-paper-100"
            aria-label="Close"
          >
            <X size={15} />
          </button>
        </header>

        <nav className="flex border-b border-ink-700 px-2">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`relative -mb-px border-b-2 px-3 py-2.5 text-[14px] font-medium transition-colors ${
                tab === t.id ? 'border-accent-400 text-paper-50' : 'border-transparent text-paper-500 hover:text-paper-200'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {tab === 'reasoning' && (
            <>
              <Field label={node.state === 'idle' ? 'Standby' : 'Current action'}>
                <p className="text-[16px] leading-relaxed text-paper-100">
                  {node.state === 'idle' ? node.idleAction : node.action}
                </p>
              </Field>
              <Field label="Input">
                <p className="mono rounded-sm border border-ink-700 bg-ink-850 px-3 py-2 text-[14px] leading-relaxed break-all text-paper-300">
                  {node.input}
                </p>
              </Field>
              <Field label="Decision &amp; reasoning">
                <p className="text-[16px] leading-relaxed text-paper-200">{node.decision}</p>
                {node.confidence !== null && (
                  <div className="mt-4">
                    <div className="mb-1.5 flex items-center justify-between">
                      <span className="text-[13.5px] text-paper-400">confidence</span>
                      <span className="mono text-[15px]">
                        {node.confidence.toFixed(2)}{' '}{'('}{node.verification_abstained ? 'abstained' : ''}{')'}
                      </span>
                    </div>
                    <div className="h-[3px] overflow-hidden rounded-full bg-ink-700">
                      <div className="anim-bar h-full"
  style={{
    width: `${node.confidence * 100}%`,
    background: node.verification_abstained ? 'bg-dim-500' : 'bg-accent-500',
  }} />
                    </div>
                  </div>
                )}
              </Field>
            </>
          )}

          {tab === 'evidence' && (
            <>
              <Field label="Verification proof">
                <div className="rounded-sm border border-ink-700 bg-ink-850/70 px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <Badge tone={statusTone(node.verification.status)}>{node.verification.status}</Badge>
                    <span className="mono text-[13px] text-paper-500">
                      {experiment.id.slice(0, 8)}/{node.id}
                    </span>
                  </div>
                  <p className="mt-2 text-[15px] leading-relaxed text-paper-300">{node.verification.note}</p>
                </div>
              </Field>
              <Field label={`Evidence used · ${node.evidence.length}`}>
                {node.evidence.length === 0 ? (
                  <p className="text-[15px] text-paper-500">
                    No evidence artifacts reported by the backend for this stage yet.
                  </p>
                ) : (
                  <ul className="flex flex-col gap-1.5">
                    {node.evidence.map((e) => (
                      <li
                        key={e}
                        className="mono flex items-start gap-2 rounded-sm border border-ink-700 bg-ink-850 px-2.5 py-1.5 text-[13.5px] leading-snug break-all text-paper-300"
                      >
                        <span className="mt-[5px] h-1 w-1 shrink-0 rounded-full bg-verify-500" />
                        {e}
                      </li>
                    ))}
                  </ul>
                )}
              </Field>
              <Field label="Audit">
                <div className="flex flex-col gap-2 text-[14px] text-paper-400">
                  <div className="flex justify-between gap-3">
                    <span>recorded</span>
                    <span className="mono text-paper-200">{formatApiDate(experiment.createdAt)}</span>
                  </div>
                  <div className="flex justify-between gap-3">
                    <span>verification level</span>
                    <span className="mono text-paper-200">{experiment.verificationLevel}</span>
                  </div>
                  <div className="flex justify-between gap-3">
                    <span>experiment status</span>
                    <span className="mono text-paper-200">{experiment.status}</span>
                  </div>
                </div>
              </Field>
            </>
          )}

          {tab === 'tools' && (
            <>
              <Field label="Tool calls">
                {node.tools.length === 0 ? (
                  <p className="text-[15px] text-paper-500">
                    Tool-call telemetry is not exposed by the backend API for this stage.
                  </p>
                ) : (
                  <div className="overflow-hidden rounded-sm border border-ink-700">
                    {node.tools.map((t, i) => (
                      <div
                        key={`${t.name}-${i}`}
                        className={`flex items-center gap-3 px-3 py-2 ${i % 2 ? 'bg-ink-850' : 'bg-ink-800/50'}`}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="mono truncate text-[14px] text-paper-100">{t.name}</div>
                          <div className="mono truncate text-[13px] text-paper-500">{t.args}</div>
                        </div>
                        <span className="mono tnum shrink-0 text-[13px] text-accent-300/90">{fmtMs(t.ms)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </Field>
              <Field label={`Stage logs · ${stageLogs.length}`}>
                {stageLogs.length === 0 ? (
                  <p className="text-[15px] text-paper-500">No log lines recorded for this stage yet.</p>
                ) : (
                  <div className="flex flex-col gap-[3px]">
                    {stageLogs.map((l) => (
                      <div key={l.id} className="anim-log-in mono flex gap-2 text-[13px] leading-relaxed">
                        <span className="shrink-0 text-paper-500">{l.ts}</span>
                        <span
                          className={`w-[58px] shrink-0 ${
                            l.level === 'VERIFY'
                              ? 'text-verify-500'
                              : l.level === 'WARN'
                                ? 'text-warn-500'
                                : l.level === 'DECISION' || l.level === 'METRIC'
                                  ? 'text-accent-300'
                                  : 'text-paper-500'
                          }`}
                        >
                          {l.level}
                        </span>
                        <span className="min-w-0 flex-1 break-words text-paper-300">{l.text}</span>
                      </div>
                    ))}
                  </div>
                )}
              </Field>
            </>
          )}

          {tab === 'analysis' && (
            <>
              {metrics.length === 0 ? (
                <div className="px-5 py-10 text-center">
                  <p className="text-[16px] text-paper-300">Analysis appears after the run completes.</p>
                  <p className="mt-2 text-[15px] leading-relaxed text-paper-500">
                    Metrics are read from <span className="mono">result_summary.ml_result</span> when the backend
                    finishes training.
                  </p>
                </div>
              ) : (
                <>
                  <Field label="Metrics (backend ml_result)">
                    <div className="grid grid-cols-3 gap-px overflow-hidden rounded-sm border border-ink-700 bg-ink-700">
                      {metrics.slice(0, 3).map((m) => (
                        <div key={m.name} className="bg-ink-900 px-3 py-2.5 text-center">
                          <div className="mono text-[12px] tracking-[0.08em] text-paper-500 uppercase">{m.name}</div>
                          <div className="mono tnum mt-1 text-[19.5px] text-paper-50">{m.value.toFixed(3)}</div>
                        </div>
                      ))}
                    </div>
                  </Field>
                  <Field label="All reported metrics">
                    <ul className="flex flex-col gap-2">
                      {metrics.map((m) => (
                        <li key={m.name} className="flex items-center gap-3">
                          <span className="mono w-[150px] shrink-0 truncate text-[13.5px] text-paper-300" title={m.name}>
                            {m.name}
                          </span>
                          <span className="h-[6px] flex-1 overflow-hidden rounded-[2px] bg-ink-800">
                            <span
                              className="anim-bar block h-full bg-accent-500"
                              style={{ width: `${(Math.abs(m.value) / maxMetric) * 100}%` }}
                            />
                          </span>
                          <span className="mono tnum w-[50px] shrink-0 text-right text-[13px] text-paper-400">
                            {m.value.toFixed(3)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </Field>
                </>
              )}
            </>
          )}
        </div>
      </aside>
    </>
  )
}
