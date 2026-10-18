/**
 * AutoSage Project Summary — what you asked, what was understood, how it went.
 *
 * Empty by design until the caller gives a project on the Objectives page.
 * Each problem statement submitted there creates a verification session, and
 * this page processes those sessions here:
 *
 *   - What you asked for — the verbatim problem statement and submitted config.
 *   - What was understood — the reading of your request, its framed problem
 *     statement, and the steps taken to resolve it.
 *   - How the process went — the stage-by-stage trail and recorded decisions.
 *   - What came out of it — the measured result of the linked pipeline run.
 *
 * The four verification objectives stay on the Objectives page; they are not
 * reported here. Everything is read-only — this page never trains, verifies,
 * or modifies an experiment. Lives in the "Operate" section of the sidebar.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Compass,
  FlaskConical,
  Inbox,
  RefreshCw,
  Route,
  ShieldCheck,
} from 'lucide-react'

import { PageHeader } from '../components/layout/Sidebar'
import { EmptyState, SectionTitle } from '../components/ui/Primitives'
import {
  api,
  type ExperimentRead,
  type ObjectiveDecisionRecord,
  type ObjectiveSessionState,
  type ObjectiveSessionSummary,
  type ObjectiveStageUpdate,
} from '../lib/api'

// ── status tones ────────────────────────────────────────────────────────────

type Tone = 'ok' | 'error' | 'warn' | 'info' | 'neutral'

const TONE_COLOR: Record<Tone, string> = {
  ok: 'var(--as-verify)',
  error: 'var(--as-error)',
  warn: 'var(--as-warn)',
  info: 'var(--as-teal)',
  neutral: 'var(--as-text-3)',
}

function toneOf(status?: string | null): Tone {
  switch (status) {
    case 'PASSED':
    case 'PASS':
    case 'COMPLETED':
      return 'ok'
    case 'FAILED':
    case 'FAIL':
      return 'error'
    case 'NOT_VERIFIED':
    case 'BLOCKED':
      return 'warn'
    case 'RUNNING':
    case 'PENDING':
    case 'QUEUED':
      return 'info'
    default:
      return 'neutral'
  }
}

function StatusChip({ status, label }: { status?: string | null; label?: string }) {
  if (!status) return null
  const t = toneOf(status)
  return (
    <span
      className="inline-flex shrink-0 items-center rounded-md px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide"
      style={{
        background: `color-mix(in oklch, ${TONE_COLOR[t]} 14%, transparent)`,
        color: TONE_COLOR[t],
        border: `1px solid color-mix(in oklch, ${TONE_COLOR[t]} 35%, transparent)`,
      }}
    >
      {label ?? status}
    </span>
  )
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function fmtPct(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${Math.round(value * 100)}%`
}

/** Defensive read of the linked experiment's measured summary. */
function readMetric(rs: Record<string, unknown> | undefined, ...path: string[]): unknown {
  let cur: unknown = rs
  for (const key of path) {
    if (cur && typeof cur === 'object' && key in (cur as Record<string, unknown>)) {
      cur = (cur as Record<string, unknown>)[key]
    } else {
      return undefined
    }
  }
  return cur
}

// ── page ────────────────────────────────────────────────────────────────────

export function ProjectSummaryPage() {
  // All state first; every hook below runs on every render (Rules of Hooks —
  // the unconditional order matters because the page has early returns later).
  const [loadingList, setLoadingList] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [sessions, setSessions] = useState<ObjectiveSessionSummary[]>([])
  const [runId, setRunId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ObjectiveSessionState | null>(null)
  const [linkedExp, setLinkedExp] = useState<ExperimentRead | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [reloadTick, setReloadTick] = useState(0)

  // 1 · discover the projects the caller gave on the Objectives page.
  useEffect(() => {
    let cancelled = false
    setLoadingList(true)
    setListError(null)

    api.listObjectiveSessions(20)
      .then((rows) => {
        if (cancelled) return
        setSessions(rows)
        // Keep the currently-selected project if it still exists, else take
        // the newest one (index 0 — the listing is newest first).
        setRunId((prev) =>
          prev && rows.some((r) => r.run_id === prev) ? prev : (rows[0]?.run_id ?? null),
        )
      })
      .catch((err) => {
        if (!cancelled) {
          setListError(err instanceof Error ? err.message : 'Failed to load projects')
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingList(false)
      })

    return () => {
      cancelled = true
    }
  }, [reloadTick])

  // 2 · load the selected project's full state, plus its linked pipeline run.
  useEffect(() => {
    let cancelled = false
    setDetail(null)
    setLinkedExp(null)
    setDetailError(null)

    if (!runId) {
      setDetailLoading(false)
      return
    }

    setDetailLoading(true)
    void (async () => {
      try {
        const state = await api.getObjectiveSession(runId)
        if (cancelled) return
        setDetail(state)

        const linkedId = state.linked_experiment_id ?? null
        if (linkedId) {
          try {
            const exp = await api.getExperiment(linkedId)
            if (!cancelled) setLinkedExp(exp)
          } catch {
            // The linked run's metrics are supplementary; never block the page.
          }
        }
      } catch (err) {
        if (!cancelled) {
          setDetailError(err instanceof Error ? err.message : 'Failed to load project detail')
        }
      } finally {
        if (!cancelled) setDetailLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [runId])

  // ── derived data (plain reads; the page's early returns happen below) ──
  const summary = sessions.find((s) => s.run_id === runId) ?? null
  const decisions: ObjectiveDecisionRecord[] = detail?.decisions ?? []
  const updates: ObjectiveStageUpdate[] = detail?.updates ?? []

  // Stage-by-stage trail, grouped but ordered by first appearance.
  const stageOrder: string[] = []
  const stageFrames = new Map<string, ObjectiveStageUpdate[]>()
  for (const u of updates) {
    if (!stageFrames.has(u.stage)) {
      stageFrames.set(u.stage, [])
      stageOrder.push(u.stage)
    }
    stageFrames.get(u.stage)!.push(u)
  }

  const hasAnyProject = sessions.length > 0

  // ── empty state: nothing given yet ──────────────────────────────────────
  if (!loadingList && !listError && !hasAnyProject) {
    return (
      <div className="flex h-full min-w-0 flex-col" style={{ background: 'var(--as-bg)' }}>
        <PageHeader title="Project Summary" subtitle="Empty until you give it a project." />
        <div className="min-h-0 flex-1 overflow-y-auto">
          <EmptyState
            variant="feature"
            icon={<Inbox size={22} />}
            title="No project given yet"
            detail="This page summarizes the project you submit on the Objectives page. Once you give a project there, it is processed here automatically — what you asked for, what was understood, how the pipeline went, and the measured result."
            action={
              <Link
                to="/objectives"
                className="flex items-center gap-2 rounded-lg px-4 py-2.5 text-[13.5px] font-semibold transition-all hover:shadow-[0_0_18px_var(--as-accent-glow)]"
                style={{
                  background: 'linear-gradient(135deg, var(--as-accent), var(--as-teal))',
                  color: 'var(--as-bg)',
                }}
              >
                <FlaskConical size={15} />
                Give a project on Objectives
              </Link>
            }
          />
          <div className="mx-auto max-w-[560px] px-6 pb-10 text-center text-[12px]" style={{ color: 'var(--as-text-3)' }}>
            A project is created by submitting a problem statement with the
            Generate &amp; Verify flow — nothing here reads or reuses previous
            experiments behind your back.
          </div>
        </div>
      </div>
    )
  }

  // ── error loading the project list ──────────────────────────────────────
  if (!loadingList && listError) {
    return (
      <div className="flex h-full min-w-0 flex-col" style={{ background: 'var(--as-bg)' }}>
        <PageHeader title="Project Summary" subtitle="Could not load your projects." />
        <div className="min-h-0 flex-1 overflow-y-auto">
          <EmptyState
            variant="feature"
            icon={<RefreshCw size={20} />}
            title="Failed to load projects"
            detail={listError}
            action={
              <button
                type="button"
                onClick={() => setReloadTick((t) => t + 1)}
                className="flex items-center gap-2 rounded-lg border px-4 py-2.5 text-[13.5px] font-semibold transition-all hover:shadow-[0_0_18px_var(--as-teal-glow)]"
                style={{
                  borderColor: 'color-mix(in oklch, var(--as-teal) 40%, transparent)',
                  color: 'var(--as-teal)',
                }}
              >
                <RefreshCw size={14} /> Retry
              </button>
            }
          />
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-w-0 flex-col" style={{ background: 'var(--as-bg)' }}>
      <PageHeader
        title="Project Summary"
        subtitle="What you asked for, what was understood, and how the process went — from your own project."
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        {/* ── project picker (one row per project you gave) ── */}
        {hasAnyProject && (
          <div
            className="flex flex-wrap items-center gap-2 border-b px-5 py-2.5"
            style={{ borderColor: 'var(--as-border)' }}
          >
            <span className="mr-1 text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--as-text-3)' }}>
              Project
            </span>
            {sessions.map((s, i) => (
              <button
                key={s.run_id}
                type="button"
                onClick={() => setRunId(s.run_id)}
                className="rounded-md px-2.5 py-1 text-[11.5px] font-medium transition-all"
                style={{
                  border: `1px solid ${s.run_id === runId ? 'color-mix(in oklch, var(--as-accent) 45%, transparent)' : 'var(--as-border)'}`,
                  background:
                    s.run_id === runId
                      ? 'color-mix(in oklch, var(--as-accent) 10%, transparent)'
                      : 'transparent',
                  color: s.run_id === runId ? 'var(--as-accent-hi)' : 'var(--as-text-2)',
                }}
              >
                #{i + 1} · {fmtDate(s.created_at)}
                <span className="ml-1.5 inline-flex">
                  <StatusChip status={s.status} />
                </span>
              </button>
            ))}
            <button
              type="button"
              onClick={() => setReloadTick((t) => t + 1)}
              title="Re-read the latest projects"
              className="ml-auto flex h-7 w-7 items-center justify-center rounded-md border transition-all hover:shadow-[0_0_12px_var(--as-teal-glow)]"
              style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-2)' }}
            >
              <RefreshCw size={13} />
            </button>
          </div>
        )}

        {loadingList && !detail && (
          <div className="px-5 py-3 text-[12.5px]" style={{ color: 'var(--as-text-3)' }}>
            Loading your projects…
          </div>
        )}

        {detailError && (
          <div
            className="flex items-center gap-2 border-b px-5 py-2.5 text-[13px]"
            style={{
              borderColor: 'var(--as-border)',
              background: 'color-mix(in oklch, var(--as-error) 10%, transparent)',
              color: 'var(--as-error)',
            }}
            role="alert"
          >
            {detailError}
          </div>
        )}

        {detailLoading && !detail && (
          <div className="px-5 py-3 text-[12.5px]" style={{ color: 'var(--as-text-3)' }}>
            Loading this project…
          </div>
        )}

        {detail && (
          <>
            {/* ── what you asked for ── */}
            <section className="border-b px-5 py-3" style={{ borderColor: 'var(--as-border)' }}>
              <SectionTitle>What you asked for</SectionTitle>
              <div className="px-4 py-3">
                <div className="mb-2 flex flex-wrap items-center gap-1.5">
                  <StatusChip status={detail.status} />
                  <StatusChip status={detail.overall_status} label={detail.overall_status ?? undefined} />
                  <span className="text-[11px]" style={{ color: 'var(--as-text-3)' }}>
                    Given {fmtDate(summary?.created_at ?? detail.created_at)} · run {detail.run_id.slice(0, 8)}…
                  </span>
                </div>
                <div
                  className="rounded-2xl border whitespace-pre-wrap px-4 py-3 text-[13px] leading-relaxed"
                  style={{
                    borderColor: 'var(--as-border)',
                    background: 'var(--as-bg-2)',
                    color: 'var(--as-text)',
                  }}
                >
                  {detail.problem_statement}
                </div>
                <div className="mt-2.5 flex flex-wrap gap-1.5 text-[11.5px]">
                  {detail.dataset_name !== '' && (
                    <span className="rounded-md border px-2 py-0.5" style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-2)' }}>
                      dataset: {detail.dataset_name}
                    </span>
                  )}
                  {typeof detail.config?.target_column === 'string' && detail.config.target_column && (
                    <span className="rounded-md border px-2 py-0.5" style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-2)' }}>
                      target: {detail.config.target_column as string}
                    </span>
                  )}
                  {typeof detail.config?.task_type === 'string' && detail.config.task_type && (
                    <span className="rounded-md border px-2 py-0.5" style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-2)' }}>
                      task: {detail.config.task_type as string}
                    </span>
                  )}
                  {typeof detail.config?.primary_metric === 'string' && detail.config.primary_metric && (
                    <span className="rounded-md border px-2 py-0.5" style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-2)' }}>
                      metric: {detail.config.primary_metric as string}
                    </span>
                  )}
                </div>
              </div>
            </section>

            {/* ── how the process went ── */}
            <section className="border-b px-5 py-3" style={{ borderColor: 'var(--as-border)' }}>
              <SectionTitle>How the process went</SectionTitle>
              <div className="px-4 py-3">
                {stageOrder.length > 0 ? (
                  <div className="space-y-2">
                    {stageOrder.map((stage) => {
                      const frames = stageFrames.get(stage) ?? []
                      const last = frames[frames.length - 1]
                      return (
                        <div
                          key={stage}
                          className="rounded-2xl border p-3"
                          style={{ borderColor: 'var(--as-border)', background: 'var(--as-bg-2)' }}
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <Route size={13} style={{ color: 'var(--as-accent-hi)' }} />
                            <span className="text-[12.5px] font-semibold" style={{ color: 'var(--as-text)' }}>
                              {stage}
                            </span>
                            <StatusChip status={last.status} />
                            <span className="ml-auto text-[10.5px]" style={{ color: 'var(--as-text-3)' }}>
                              {frames.length} frame{frames.length === 1 ? '' : 's'} · {fmtDate(last.emitted_at)}
                            </span>
                          </div>
                          <div className="mt-1.5 space-y-1">
                            {frames.slice(0, 8).map((f, i) => {
                              const t = toneOf(f.status)
                              return (
                                <div key={`${f.emitted_at}-${i}`} className="flex items-start gap-2">
                                  <span
                                    className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                                    style={{ background: TONE_COLOR[t] }}
                                    aria-hidden
                                  />
                                  <div className="min-w-0 flex-1 text-[12px]" style={{ color: 'var(--as-text-2)' }}>
                                    {f.message}
                                  </div>
                                </div>
                              )
                            })}
                            {frames.length > 8 && (
                              <div className="text-[11px]" style={{ color: 'var(--as-text-3)' }}>
                                + {frames.length - 8} more frames for this stage.
                              </div>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="text-[12.5px]" style={{ color: 'var(--as-text-3)' }}>
                    No progress trail was recorded for this run.
                  </div>
                )}

                {decisions.length > 0 && (
                  <div className="mt-3">
                    <div className="mb-1.5 flex items-center gap-2">
                      <Compass size={13} style={{ color: 'var(--as-teal)' }} />
                      <span className="text-[12px] font-semibold" style={{ color: 'var(--as-text)' }}>
                        Decisions recorded ({decisions.length})
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      {decisions.map((d, i) => (
                        <div
                          key={`${d.category}-${i}`}
                          className="rounded-lg border px-3 py-2"
                          style={{ borderColor: 'var(--as-border)', background: 'var(--as-bg)' }}
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-md border px-1.5 py-0.5 text-[10px] uppercase tracking-wide" style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-3)' }}>
                              {d.category}
                            </span>
                            <span className="text-[12px] font-medium" style={{ color: 'var(--as-text)' }}>
                              {d.decision}
                            </span>
                            {typeof d.confidence === 'number' && (
                              <span className="mono text-[10.5px]" style={{ color: 'var(--as-text-3)' }}>
                                {fmtPct(d.confidence)} conf.
                              </span>
                            )}
                          </div>
                          {d.rationale && (
                            <div className="mt-1 text-[11.5px] leading-relaxed" style={{ color: 'var(--as-text-2)' }}>
                              {d.rationale}
                            </div>
                          )}
                          {d.source && (
                            <div className="mt-0.5 break-all text-[10.5px]" style={{ color: 'var(--as-accent-hi)' }}>
                              source: {d.source}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </section>

            {/* ── what came out of it (linked pipeline run) ── */}
            <section className="border-b px-5 py-3" style={{ borderColor: 'var(--as-border)' }}>
              <SectionTitle>What came out of it</SectionTitle>
              <div className="px-4 py-3">
                {linkedExp ? (
                  <div className="rounded-2xl border p-3" style={{ borderColor: 'var(--as-border)', background: 'var(--as-bg-2)' }}>
                    <div className="flex flex-wrap items-center gap-2">
                      <FlaskConical size={13} style={{ color: 'var(--as-violet)' }} />
                      <span className="text-[12.5px] font-semibold" style={{ color: 'var(--as-text)' }}>
                        {linkedExp.name}
                      </span>
                      <StatusChip status={linkedExp.status} />
                      <span className="ml-auto text-[10.5px]" style={{ color: 'var(--as-text-3)' }}>
                        finished {fmtDate(linkedExp.completed_at)}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11.5px]">
                      {(() => {
                        const rs = linkedExp.result_summary
                        const metric = readMetric(rs, 'ml_result', 'primary_metric')
                        const score = readMetric(rs, 'ml_result', 'primary_score')
                        const model = readMetric(rs, 'ml_result', 'selected_model')
                        return (
                          <>
                            {metric !== undefined && score !== undefined && (
                              <span className="rounded-md border px-2 py-0.5" style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-2)' }}>
                                {String(metric)}: {String(score)}
                              </span>
                            )}
                            {typeof model === 'string' && (
                              <span className="rounded-md border px-2 py-0.5" style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-2)' }}>
                                model: {model}
                              </span>
                            )}
                          </>
                        )
                      })()}
                      <Link
                        to="/experiments"
                        className="ml-auto flex items-center gap-1 text-[11.5px] font-medium transition-colors hover:text-[var(--as-accent-hi)]"
                        style={{ color: 'var(--as-accent-hi)' }}
                      >
                        open in Experiments <ShieldCheck size={11} />
                      </Link>
                    </div>
                  </div>
                ) : (
                  <div className="text-[12.5px]" style={{ color: 'var(--as-text-3)' }}>
                    {summary?.linked_experiment_id
                      ? 'The linked pipeline run is being read…'
                      : summary?.status === 'PENDING' || summary?.status === 'RUNNING'
                        ? 'This session has not finished yet — linked pipeline results appear here once available.'
                        : 'No pipeline experiment is linked to this project yet.'}
                  </div>
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  )
}
