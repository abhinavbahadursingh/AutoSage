/**
 * AutoSage Evidence — Decision-Research Workspace.
 *
 * The detailed counterpart to the Objectives overview: everything recorded
 * about *why* the generated pipeline is designed the way it is, and what the
 * verification could and could not prove.
 *
 * Contents, all sourced from the backend session record
 * (GET /objective-verification/sessions/{run_id}) or the live SSE stream of
 * that same session:
 *   - the design summary: algorithm, hyperparameters, metrics, validation
 *     strategy, assumptions, alternatives;
 *   - the individual decision records, each with its rationale, confidence
 *     and source *only when the model genuinely produced them*;
 *   - the full per-check verification results under the four objectives,
 *     with evidence kind (repository / probe / session / generated /
 *     empirical), verification level, and explicit missing-evidence notes;
 *   - the evidence-mix summary of the final report.
 *
 * Structure: a verdict band answers *what the verification concluded* first —
 * the verdict, its confidence, the tally drawn as one proportion, and the
 * problem the session was given — then the reasoning (design decisions), then
 * the receipts (per-objective checks), then what could not be proven.
 *
 * The run id arrives via ?run=<id> (links from the Objectives page) and
 * sessionStorage is only a convenience pointer for sidebar navigation —
 * the data itself always comes from the backend, so a stale tab can never
 * show another session's results.
 *
 * Nothing here was executed: these are design-time records and honest
 * verification verdicts, not measured training results.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle,
  Code2,
  ExternalLink,
  FlaskConical,
  GitBranch,
  Loader2,
  Radio,
  SearchCheck,
  ShieldCheck,
} from 'lucide-react'

import {
  api,
  ApiError,
  type ObjectiveCheckResult,
  type ObjectiveDesignRecord,
  type ObjectiveStageStatus,
  type ObjectiveVerificationReport,
} from '../lib/api'
import { EmptyState } from '../components/ui/Primitives'
import { PageHeader } from '../components/layout/Sidebar'
import {
  CATEGORY_META,
  CHECK_META,
  STAGE_META,
  ConfidenceMeter,
  DecisionCard,
  DecisionExplorer,
  stamp,
} from '../components/verification/ObjectiveViews'
import { recallObjectiveRun } from '../lib/objectiveRun'

type StageState = ObjectiveStageStatus

const TALLY_ORDER = ['PASS', 'FAIL', 'NOT_VERIFIED', 'BLOCKED'] as const

/** One hue per evidence kind, drawn from tokens the system already owns. */
const CATEGORY_COLOR: Record<string, string> = {
  source: 'var(--as-teal)',
  probe: 'var(--as-accent)',
  session: 'var(--as-text-3)',
  generated: 'var(--as-warn)',
  empirical: 'var(--as-verify)',
}

interface Part {
  key: string
  value: number
  color: string
}

/**
 * A distribution drawn as one proportion. Segments are widths of the whole, so
 * the shape carries the ratio the counts only state. Zero counts render no
 * segment rather than a misleading sliver.
 */
function ShareBar({
  parts,
  height = 8,
  animate = false,
}: {
  parts: Part[]
  height?: number
  animate?: boolean
}) {
  const total = parts.reduce((a, p) => a + p.value, 0)
  if (total <= 0) {
    return <div className="w-full rounded-full" style={{ height, background: 'var(--as-border)' }} />
  }
  let shown = -1
  return (
    <div
      className="flex w-full overflow-hidden rounded-full"
      style={{ height, background: 'var(--as-border)' }}
      role="presentation"
    >
      {parts.map((p) => {
        if (p.value <= 0) return null
        shown += 1
        return (
          <div
            key={p.key}
            className={`h-full ${animate ? 'anim-bar' : ''}`}
            style={{
              width: `${(p.value / total) * 100}%`,
              background: p.color,
              animationDelay: animate ? `${shown * 85}ms` : undefined,
            }}
          />
        )
      })}
    </div>
  )
}

export function EvidencePage() {
  const [searchParams] = useSearchParams()
  const runIdParam = searchParams.get('run')
  const runId = runIdParam || recallObjectiveRun()

  const [loading, setLoading] = useState(!!runId)
  const [error, setError] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)

  const [problem, setProblem] = useState<string>('')
  const [status, setStatus] = useState<string>('PENDING')
  const [report, setReport] = useState<ObjectiveVerificationReport | null>(null)
  const [design, setDesign] = useState<ObjectiveDesignRecord | null>(null)
  const [checks, setChecks] = useState<ObjectiveCheckResult[]>([])

  const unsubscribeRef = useRef<(() => void) | null>(null)

  // ── hydrate from the durable backend session record ─────────────────────
  useEffect(() => {
    let cancelled = false
    if (!runId) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    void (async () => {
      try {
        const state = await api.getObjectiveSession(runId)
        if (cancelled) return
        setProblem(state.problem_statement)
        setStatus(state.status)
        setReport(state.report)
        // Prefer the persisted design record; fall back to the report's copy.
        setDesign(state.design ?? state.report?.design ?? null)
        // Rebuild per-check results from the replayed frames so a late
        // subscriber sees every check, not only the ones the report carries.
        const fromFrames: ObjectiveCheckResult[] = []
        for (const update of state.updates ?? []) {
          if (update.check) fromFrames.push(update.check)
        }
        const reportChecks =
          state.report?.objectives.flatMap((o) => o.checks) ?? []
        setChecks(reportChecks.length > 0 ? reportChecks : fromFrames)
        // A completed session needs no live stream; a running one does.
        if (state.running) subscribe()
        else setStatus(state.status)
      } catch (err) {
        if (cancelled) return
        setError(err instanceof ApiError ? err.message : 'Could not load this session')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
      unsubscribeRef.current?.()
      unsubscribeRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId])

  // ── live updates while the session is still running ─────────────────────
  const applyStage = useCallback((update: { stage: string; status: StageState; check?: ObjectiveCheckResult | null; payload?: Record<string, unknown> | null }) => {
    if (update.check) {
      setChecks((prev) => {
        const others = prev.filter((c) => c.check_id !== update.check!.check_id)
        return [...others, update.check!]
      })
    }
    if (update.stage === 'code_generation' && update.payload) {
      const designRecord = update.payload.design as ObjectiveDesignRecord | undefined
      if (designRecord) setDesign((prev) => ({ ...(prev ?? {}), ...designRecord }))
    }
  }, [])

  const subscribe = useCallback(() => {
    if (!runId || unsubscribeRef.current) return
    setConnected(true)
    unsubscribeRef.current = api.streamObjectiveSession(runId, {
      onOpen: () => setConnected(true),
      onStage: (u) => applyStage(u),
      onReport: (r) => {
        setReport(r)
        if (r.design) setDesign(r.design)
        setStatus('COMPLETED')
        setConnected(false)
      },
      onError: (message) => {
        setError(message)
        setConnected(false)
      },
    })
  }, [runId, applyStage])

  // ── derived views ──────────────────────────────────────────────────────
  const objectives = useMemo(() => report?.objectives ?? [], [report])
  const totals = useMemo(() => {
    const out: Record<string, number> = { PASS: 0, FAIL: 0, NOT_VERIFIED: 0, BLOCKED: 0 }
    if (report) {
      for (const key of Object.keys(out)) out[key] = report.totals?.[key] ?? 0
    } else {
      for (const c of checks) out[c.status] = (out[c.status] ?? 0) + 1
    }
    return out
  }, [report, checks])

  // Group streamed checks under their objective while the report is pending.
  const liveByObjective = useMemo(() => {
    if (objectives.length > 0) return []
    const byStage = new Map<string, ObjectiveCheckResult[]>()
    for (const c of checks) {
      const key = c.check_id.split('_').slice(0, 2).join('_')
      const list = byStage.get(key) ?? []
      list.push(c)
      byStage.set(key, list)
    }
    return [...byStage.entries()]
  }, [objectives, checks])

  const missingEvidence = useMemo(
    () => (report ? report.objectives.flatMap((o) => o.checks) : checks).filter((c) => c.status === 'NOT_VERIFIED'),
    [report, checks],
  )

  // ── verdict band figures (derived from the same numbers, never restated) ─
  const decided = TALLY_ORDER.reduce((a, s) => a + (totals[s] ?? 0), 0)
  const verdict = report ? STAGE_META[report.overall_status] ?? STAGE_META.PENDING : null
  const verdictLine = !report
    ? ''
    : decided === 0
      ? 'No checks have been decided for this session yet.'
      : [
          `${totals.PASS ?? 0} of ${decided} checks passed`,
          totals.FAIL ? `${totals.FAIL} failed` : null,
          totals.NOT_VERIFIED
            ? `${totals.NOT_VERIFIED} could not be verified from the records this session produced`
            : null,
          totals.BLOCKED ? `${totals.BLOCKED} blocked` : null,
        ]
          .filter(Boolean)
          .join(', ') + '.'

  const mixParts: Part[] = Object.entries(report?.evidence_categories ?? {})
    .filter(([cat]) => CATEGORY_META[cat])
    .map(([cat, n]) => ({
      key: cat,
      value: Number(n) || 0,
      color: CATEGORY_COLOR[cat] ?? 'var(--as-accent)',
    }))

  if (!runId) {
    return (
      <div className="flex h-full min-w-0 flex-col" style={{ background: 'var(--as-bg)' }}>
        <PageHeader
          title="Evidence"
          subtitle="Decision research for an objective-verification session."
        />
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center">
            <EmptyState
              variant="feature"
              icon={<SearchCheck size={20} />}
              title="No verification session selected"
              detail="Start a verification on the Objectives page, then open its evidence from there — each session's evidence is scoped to its own run id."
              action={
                <Link to="/objectives" className="btn-pill btn-primary">
                  <FlaskConical size={14} /> Go to Objectives
                </Link>
              }
            />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-w-0 flex-col" style={{ background: 'var(--as-bg)' }}>
      <PageHeader
        title="Evidence"
        subtitle="Recorded design decisions, their rationale, and what the verification could and could not prove."
        right={
          <div className="flex items-center gap-2">
            {connected && (
              <span
                className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium"
                style={{ borderColor: 'var(--as-border-hi)', color: 'var(--as-teal)' }}
              >
                <Radio size={10} className="animate-pulse" /> live
              </span>
            )}
            <span
              className="mono rounded-md border px-2 py-0.5 text-[11px]"
              style={{ borderColor: 'var(--as-border-hi)', color: 'var(--as-text-2)' }}
              title="This evidence is scoped to this verification session"
            >
              run {runId.slice(0, 8)}
            </span>
            <Link
              to={`/objectives`}
              className="flex h-[28px] items-center gap-1.5 rounded-md border px-2.5 text-[13px] transition-colors hover:border-[var(--as-accent)]"
              style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-2)' }}
            >
              <FlaskConical size={13} /> Objectives
            </Link>
            <Link
              to={`/sandbox?run=${encodeURIComponent(runId)}`}
              className="flex h-[28px] items-center gap-1.5 rounded-md border px-2.5 text-[13px] transition-colors hover:border-[var(--as-accent)]"
              style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-2)' }}
              title="View the generated code for this session"
            >
              <Code2 size={13} /> Sandbox
            </Link>
          </div>
        }
      />

      {error && (
        <div
          className="flex items-start gap-2 border-b px-5 py-2.5"
          style={{
            borderColor: 'var(--as-border)',
            background: 'color-mix(in oklch, var(--as-error) 10%, transparent)',
          }}
          role="alert"
        >
          <AlertTriangle size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--as-error)' }} />
          <div className="min-w-0 flex-1">
            <div className="text-[13px] font-medium" style={{ color: 'var(--as-error)' }}>
              Could not load evidence
            </div>
            <div className="text-[12.5px]" style={{ color: 'var(--as-text-2)' }}>{error}</div>
          </div>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <EmptyState
            icon={<Loader2 size={19} className="animate-spin" />}
            title="Loading session evidence..."
            detail={`Fetching the backend record for run ${runId.slice(0, 8)}.`}
          />
        ) : (
          <>
            {/* ── verdict band: what the verification concluded ─────────── */}
            <section
              className="anim-fade-up relative overflow-hidden border-b"
              style={{ borderColor: 'var(--as-border)' }}
            >
              <div className="grid-fade pointer-events-none absolute inset-0 opacity-45" aria-hidden />
              {verdict && (
                <div
                  className="pointer-events-none absolute inset-0"
                  style={{
                    background: `radial-gradient(115% 150% at 3% 0%, color-mix(in oklch, ${verdict.color} 16%, transparent), transparent 58%)`,
                  }}
                  aria-hidden
                />
              )}
              <div className="relative px-5 pb-5 pt-5">
                {report && verdict && (
                  <>
                    <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-5">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2.5">
                          <verdict.Icon
                            size={24}
                            className="shrink-0"
                            style={{ color: verdict.color }}
                          />
                          <h2
                            className="text-[27px] font-semibold leading-none tracking-[-0.03em]"
                            style={{ color: 'var(--as-text)' }}
                          >
                            {verdict.label}
                          </h2>
                        </div>
                        <p
                          className="mt-2.5 max-w-[70ch] text-[13px] leading-relaxed"
                          style={{ color: 'var(--as-text-2)' }}
                        >
                          {verdictLine}
                        </p>
                      </div>

                      <div className="shrink-0">
                        <div className="label-xs">Confidence</div>
                        <div className="mt-1.5 flex items-center gap-3">
                          <span
                            className="mono tnum text-[26px] leading-none"
                            style={{ color: 'var(--as-text)' }}
                          >
                            {Math.round((report.overall_confidence ?? 0) * 100)}%
                          </span>
                          <ConfidenceMeter
                            value={report.overall_confidence}
                            color={verdict.color}
                            width={124}
                            animated
                            showValue={false}
                          />
                        </div>
                      </div>
                    </div>

                    {/* the tally as one proportion */}
                    <div className="mt-5">
                      <ShareBar
                        animate
                        parts={TALLY_ORDER.map((s) => ({
                          key: s,
                          value: totals[s] ?? 0,
                          color: CHECK_META[s].color,
                        }))}
                      />
                      <ul className="mt-2.5 flex flex-wrap items-center gap-x-5 gap-y-1.5">
                        {TALLY_ORDER.map((s) => (
                          <li
                            key={s}
                            className="flex items-center gap-1.5 text-[12px]"
                            style={{ color: 'var(--as-text-2)' }}
                          >
                            <span
                              className="h-1.5 w-1.5 shrink-0 rounded-full"
                              style={{ background: CHECK_META[s].color }}
                            />
                            <span className="mono tnum text-[12.5px]" style={{ color: 'var(--as-text)' }}>
                              {totals[s] ?? 0}
                            </span>
                            <span>{s === 'NOT_VERIFIED' ? 'not verified' : s.toLowerCase()}</span>
                          </li>
                        ))}
                        <li className="mono ml-auto text-[11.5px]" style={{ color: 'var(--as-text-3)' }}>
                          {report.started_at || report.completed_at
                            ? `${stamp(report.started_at)}–${stamp(report.completed_at)}`
                            : '--:--:--'}
                        </li>
                      </ul>
                    </div>
                  </>
                )}

                <div
                  className={report ? 'mt-5 border-t pt-4' : ''}
                  style={report ? { borderColor: 'var(--as-border)' } : undefined}
                >
                  <div className="label-xs">Problem</div>
                  <p
                    className="mt-1 max-w-[74ch] text-[13.5px] leading-relaxed"
                    style={{ color: problem ? 'var(--as-text)' : 'var(--as-text-3)' }}
                  >
                    {problem || 'not recorded'}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
                    {report?.dataset_name && (
                      <span
                        className="mono rounded-md border px-2 py-[3px] text-[11px]"
                        style={{ borderColor: 'var(--as-border-hi)', color: 'var(--as-text-2)' }}
                        title="Dataset for this session"
                      >
                        {report.dataset_name}
                      </span>
                    )}
                    <span
                      className="rounded-md border px-2 py-[3px] text-[11px] font-medium"
                      style={{ borderColor: 'var(--as-border-hi)', color: 'var(--as-text-2)' }}
                    >
                      {status}
                    </span>
                  </div>
                </div>
              </div>
            </section>

            {/* ── evidence mix: what the verdict is built on ────────────── */}
            {report &&
              (report.evidence_categories ?? Object.keys(report.verification_levels ?? {}).length > 0) && (
                <div
                  className="border-b px-5 py-3"
                  style={{ borderColor: 'var(--as-border)' }}
                >
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                    <span className="label-xs shrink-0">Evidence mix</span>
                    {mixParts.length > 0 && (
                      <span className="min-w-[160px] flex-1">
                        <ShareBar height={4} parts={mixParts} />
                      </span>
                    )}
                    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
                      {Object.entries(report.evidence_categories ?? {}).map(([cat, n]) => {
                        const meta = CATEGORY_META[cat]
                        if (!meta) return null
                        return (
                          <li
                            key={cat}
                            className="flex items-center gap-1.5 text-[11.5px]"
                            style={{ color: 'var(--as-text-2)' }}
                          >
                            <span
                              className="h-1.5 w-1.5 shrink-0 rounded-full"
                              style={{ background: CATEGORY_COLOR[cat] ?? 'var(--as-accent)' }}
                            />
                            <span className="mono tnum" style={{ color: 'var(--as-text)' }}>
                              {n}
                            </span>
                            <span title={meta.hint}>{meta.label}</span>
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                  <p
                    className="mt-2 max-w-[110ch] text-[11.5px] italic leading-relaxed"
                    style={{ color: 'var(--as-text-2)' }}
                  >
                    A repository-level pass confirms a capability exists in source — it does not
                    prove a specific generated decision is correct.
                  </p>
                </div>
              )}

            {/* ── design decisions ────────────────────────────────────── */}
            {!loading && !design && status === 'COMPLETED' && (
              <div className="px-4 pt-5">
                <div
                  className="flex items-start gap-2 rounded-2xl border px-4 py-3"
                  style={{
                    borderColor: 'color-mix(in oklch, var(--as-warn) 28%, transparent)',
                    background: 'color-mix(in oklch, var(--as-warn) 7%, transparent)',
                  }}
                >
                  <AlertTriangle size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--as-warn)' }} />
                  <p className="text-[12.5px] leading-relaxed" style={{ color: 'var(--as-text-2)' }}>
                    No design record was produced for this session — the model did not return a
                    parseable design, or code generation failed. No record is invented to fill the gap.
                  </p>
                </div>
              </div>
            )}
            <DecisionExplorer design={design} />

            {/* ── per-objective check detail ──────────────────────────── */}
            {objectives.length > 0 ? (
              <div className="space-y-4 px-4 pb-5 pt-1">
                {objectives.map((objective) => {
                  const meta = STAGE_META[objective.status] ?? STAGE_META.PENDING
                  return (
                    <section
                      key={objective.id}
                      className="overflow-hidden rounded-2xl border"
                      style={{ borderColor: 'var(--as-border)', background: 'var(--as-bg-2)' }}
                    >
                      <header
                        className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b px-4 py-3"
                        style={{ borderColor: 'var(--as-border)' }}
                      >
                        <span className="flex shrink-0 items-center gap-1.5">
                          <GitBranch size={12} style={{ color: 'var(--as-text-3)' }} />
                          <span
                            className="mono text-[10.5px] uppercase tracking-[0.12em]"
                            style={{ color: 'var(--as-text-3)' }}
                          >
                            Objective {objective.number}
                          </span>
                        </span>
                        <h3
                          className="min-w-[10rem] flex-1 text-[14.5px] font-semibold leading-snug tracking-tight"
                          style={{ color: 'var(--as-text)' }}
                        >
                          {objective.title}
                        </h3>
                        <ConfidenceMeter
                          value={objective.confidence}
                          color={meta.color}
                          width={64}
                        />
                        <span
                          className="inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-[1px] text-[9.5px] font-semibold uppercase tracking-wider"
                          style={{
                            color: meta.color,
                            background: `color-mix(in oklch, ${meta.color} 14%, transparent)`,
                            borderColor: `color-mix(in oklch, ${meta.color} 34%, transparent)`,
                          }}
                        >
                          {meta.label}
                        </span>
                      </header>
                      <p
                        className="px-4 pt-3 text-[12.5px] leading-relaxed"
                        style={{ color: 'var(--as-text-2)' }}
                      >
                        {objective.statement}
                      </p>
                      <div className="mt-2">
                        {objective.checks.map((check) => (
                          <DecisionCard key={check.check_id} check={check} />
                        ))}
                      </div>
                    </section>
                  )
                })}
              </div>
            ) : liveByObjective.length > 0 ? (
              <div className="space-y-4 px-4 pb-5 pt-1">
                {liveByObjective.map(([stage, stageChecks]) => (
                  <section
                    key={stage}
                    className="overflow-hidden rounded-2xl border"
                    style={{ borderColor: 'var(--as-border)', background: 'var(--as-bg-2)' }}
                  >
                    <header
                      className="flex items-center gap-2 border-b px-4 py-3"
                      style={{ borderColor: 'var(--as-border)' }}
                    >
                      <GitBranch size={12} style={{ color: 'var(--as-text-3)' }} />
                      <span
                        className="mono text-[10.5px] uppercase tracking-[0.12em]"
                        style={{ color: 'var(--as-text-3)' }}
                      >
                        {stage.replace(/_/g, ' ')}
                      </span>
                      <span
                        className="mono ml-auto text-[11px]"
                        style={{ color: 'var(--as-text-3)' }}
                      >
                        {stageChecks.length} check(s)
                      </span>
                    </header>
                    <div>
                      {stageChecks.map((check) => (
                        <DecisionCard key={check.check_id} check={check} />
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            ) : (
              !loading && (
                <EmptyState
                  variant="feature"
                  icon={<SearchCheck size={20} />}
                  title="No check results recorded yet"
                  detail="The session accepted the input but has not produced check results. If it is still running, results stream in live."
                />
              )
            )}

            {/* ── missing evidence ────────────────────────────────────── */}
            {missingEvidence.length > 0 && (
              <div className="px-4 pb-5">
                <section
                  className="rounded-2xl border px-4 py-4"
                  style={{
                    borderColor: 'color-mix(in oklch, var(--as-warn) 28%, transparent)',
                    background: 'color-mix(in oklch, var(--as-warn) 7%, transparent)',
                  }}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <AlertTriangle size={14} style={{ color: 'var(--as-warn)' }} />
                    <h3
                      className="text-[14px] font-semibold tracking-tight"
                      style={{ color: 'var(--as-text)' }}
                    >
                      Missing Evidence
                    </h3>
                    <span
                      className="mono ml-auto text-[11.5px]"
                      style={{ color: 'var(--as-warn)' }}
                    >
                      {missingEvidence.length} check(s)
                    </span>
                  </div>
                  <p
                    className="mt-2 max-w-[86ch] text-[12.5px] leading-relaxed"
                    style={{ color: 'var(--as-text-2)' }}
                  >
                    These checks could not be verified from the records a design-time session
                    produces. They are reported as NOT VERIFIED, never as a pass. Expand any check
                    above to see exactly what was found and what is missing.
                  </p>
                  <ul className="mt-3">
                    {missingEvidence.map((check) => (
                      <li
                        key={check.check_id}
                        className="flex items-center gap-2.5 border-b py-1.5 text-[12.5px] last:border-b-0"
                        style={{ borderColor: 'color-mix(in oklch, var(--as-warn) 18%, transparent)' }}
                      >
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-full"
                          style={{ background: 'var(--as-warn)' }}
                        />
                        <span className="min-w-0 flex-1 truncate" style={{ color: 'var(--as-text-2)' }}>
                          {check.title}
                        </span>
                        <span className="mono shrink-0 text-[11px]" style={{ color: 'var(--as-text-2)' }}>
                          {check.check_id}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              </div>
            )}

            {/* ── footer note ─────────────────────────────────────────── */}
            <div
              className="flex flex-wrap items-center gap-2 border-t px-5 py-3.5 text-[11.5px]"
              style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-2)' }}
            >
              <ShieldCheck size={12} className="shrink-0" />
              <span>
                Everything on this page is scoped to verification session{' '}
                <span className="mono">{runId.slice(0, 8)}</span> and was produced without
                executing generated code or training a model.
              </span>
              {report && (
                <Link
                  to={`/sandbox?run=${encodeURIComponent(runId)}`}
                  className="ml-auto flex items-center gap-1 transition-colors hover:text-[var(--as-teal)]"
                >
                  <ExternalLink size={11} /> View generated code
                </Link>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
