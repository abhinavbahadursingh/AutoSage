/**
 * AutoSage Objective Verification — Overview & Orchestration Page.
 *
 * The user's only required input is a natural-language ML problem description.
 * No dataset, target column, preprocessing configuration, or training is
 * required. This page starts a verification session on the backend, streams
 * its progress over SSE, and summarizes the four canonical objectives with
 * their real statuses.
 *
 * Information-architecture split (this page is the *overview*):
 *   - Objectives (here): input, orchestration, live progress, final summary.
 *   - Sandbox: the generated code itself, editable; Run executes only a
 *     Python file the user has created or edited, in the Docker sandbox.
 *   - Evidence: the detailed decision research — rationale, alternatives,
 *     per-check evidence and missing evidence.
 *
 * Both sibling pages are reached with this session's run id, and load their
 * data from the backend session record (GET /sessions/{run_id}) — never from
 * a page-local copy that could go stale.
 *
 * Generated code is NEVER executed automatically anywhere in this flow. The
 * only execution offered is the user running their own edited copy from the
 * Sandbox, against the isolated Docker sandbox.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  CircleSlash,
  Code2,
  ExternalLink,
  FlaskConical,
  GitBranch,
  Loader2,
  Radio,
  RotateCw,
  ShieldCheck,
  Terminal,
} from 'lucide-react'

import {
  api,
  ApiError,
  type FreshSessionCreate,
  type ObjectiveCheckStatus,
  type ObjectiveDefinition,
  type ObjectiveResult,
  type ObjectiveStageUpdate,
  type ObjectiveVerificationReport,
} from '../lib/api'
import { EmptyState, SectionTitle } from '../components/ui/Primitives'
import { setPipelinePlanDraft } from '../lib/pipelinePlanStore'
import {
  forgetObjectiveRun,
  recallObjectiveRun,
  rememberObjectiveRun,
} from '../lib/objectiveRun'
import { PageHeader } from '../components/layout/Sidebar'
import {
  CATEGORY_META,
  CHECK_META,
  STAGE_META,
  CategoryTag,
  CheckPill,
  stamp,
  type StageState,
} from '../components/verification/ObjectiveViews'

// ── session pointer ──────────────────────────────────────────────────────
//
// `rememberObjectiveRun` / `recallObjectiveRun` / `forgetObjectiveRun` live in
// lib/objectiveRun — the pointer is shared with the Sandbox and Evidence
// pages and with this page's own remount-restore.

// ── input form ───────────────────────────────────────────────────────────

const EXAMPLE_PROBLEMS = [
  {
    id: 'churn',
    label: 'Customer Churn',
    description: 'Predict which customers will churn next month based on usage and billing history.',
  },
  {
    id: 'price',
    label: 'House Price',
    description: 'Estimate house prices based on square footage, location, and features.',
  },
  {
    id: 'spam',
    label: 'Spam Detection',
    description: 'Classify SMS messages as spam or not-spam using text content.',
  },
]

function ProblemInput({
  onSubmit,
  busy,
  hint,
  compact = false,
  prompt,
}: {
  onSubmit: (problem: string) => void
  busy: boolean
  hint?: string
  /**
   * A session is already on screen, or one is starting. The full block
   * (header, 3-row field, examples, button) would push the results below the
   * fold, so it starts as a single line and only unfolds once the user
   * reaches for it.
   */
  compact?: boolean
  /**
   * The prompt this session was started from. Whenever the field is empty —
   * folded or unfolded, starting or finished — it echoes the prompt as its
   * placeholder, so the box always reads as the query that is running (or
   * ran) instead of a generic hint.
   */
  prompt?: string | null
}) {
  const [problem, setProblem] = useState('')
  const [focused, setFocused] = useState(false)

  const valid = problem.trim().length >= 8

  // The empty field echoes the prompt this session was started from — while
  // it starts and after it finishes, folded or unfolded. Keep it to one
  // readable line; the full text stays on the field's tooltip.
  const promptText = prompt?.trim() ?? ''
  const promptHint = promptText.length > 160 ? `${promptText.slice(0, 159)}…` : promptText

  // Unfold only on intent (focus) or while there is text — collapsing on blur
  // with text present would move the button out from under the click.
  const expanded = !compact || focused || problem.trim().length > 0

  return (
    <div
      className={`border-b ${expanded ? 'px-5 py-5' : 'px-5 py-2.5'}`}
      style={{ borderColor: 'var(--as-border)' }}
    >
      {expanded && (
        <div className="mb-3 flex items-center gap-2">
          <ShieldCheck size={14} style={{ color: 'var(--as-accent)' }} />
          <span className="text-[13px] font-medium" style={{ color: 'var(--as-text-2)' }}>
            Describe your ML problem
          </span>
        </div>
      )}

      <div className={expanded ? '' : 'flex items-center gap-3'}>
        <textarea
          value={problem}
          onChange={(e) => setProblem(e.target.value)}
          placeholder={
            promptHint ||
            (expanded
              ? 'e.g. Predict which customers will churn next month based on usage and billing history...'
              : 'Describe a new ML problem — it starts a new session.')
          }
          title={promptText && promptHint !== promptText ? promptText : undefined}
          rows={expanded ? 3 : 1}
          className={`w-full resize-none rounded-lg border outline-none transition-colors ${
            expanded
              ? 'px-3.5 py-3 text-[14px] leading-relaxed'
              : 'min-h-[36px] flex-1 px-3 py-2 text-[13.5px] leading-snug'
          }`}
          style={{
            borderColor: 'var(--as-border-hi)',
            background: 'var(--as-bg-2)',
            color: 'var(--as-text)',
          }}
          onFocus={(e) => {
            setFocused(true)
            e.currentTarget.style.borderColor = 'var(--as-accent)'
          }}
          onBlur={(e) => {
            setFocused(false)
            e.currentTarget.style.borderColor = 'var(--as-border-hi)'
          }}
        />

        {expanded && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="text-[12px]" style={{ color: 'var(--as-text-3)' }}>
              Try an example:
            </span>
            {EXAMPLE_PROBLEMS.map((ex) => (
              <button
                key={ex.id}
                type="button"
                // Keep focus in the field: blurring with an empty value would
                // collapse the block and move this chip out from under the click.
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => setProblem(ex.description)}
                className="rounded-full border px-3 py-1 text-[12px] font-medium transition-all hover:shadow-[0_0_12px_var(--as-accent-glow)]"
                style={{
                  borderColor: 'var(--as-border-hi)',
                  background: 'var(--as-bg-2)',
                  color: 'var(--as-text-2)',
                }}
                title={ex.description}
              >
                {ex.label}
              </button>
            ))}
          </div>
        )}

        <div className={expanded ? 'mt-4 flex items-center gap-3' : 'shrink-0'}>
          <button
            type="button"
            disabled={!valid || busy}
            onClick={() => {
              if (!valid) return
              // Hand the prompt over and reset the field: the submitted text
              // lives in the session bar above, and leaving it here would pin
              // the block open (text forces the expanded layout) instead of
              // minimising to the single line.
              onSubmit(problem.trim())
              setProblem('')
            }}
            className="flex h-[36px] items-center gap-2 rounded-lg px-5 text-[13.5px] font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-40"
            style={{
              background: 'var(--as-accent)',
              color: '#fff',
              boxShadow: valid && !busy ? '0 4px 16px var(--as-accent-glow)' : 'none',
            }}
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
            {busy ? 'Verifying...' : 'Generate & Verify'}
          </button>
          {expanded && !valid && problem.length > 0 && (
            <span className="text-[12px]" style={{ color: 'var(--as-text-3)' }}>
              At least 8 characters
            </span>
          )}
          {expanded && valid && hint && (
            <span className="text-[12px]" style={{ color: 'var(--as-text-3)' }}>
              {hint}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

// ── workflow timeline ────────────────────────────────────────────────────

function WorkflowTimeline({
  objectives,
  stageStates,
  checkStatuses,
  outcomes,
  activeObjective,
  onSelect,
}: {
  objectives: ObjectiveDefinition[]
  stageStates: Record<string, StageState>
  checkStatuses: Record<string, ObjectiveCheckStatus>
  /**
   * Final per-objective results once the report exists. The row then shows
   * the verdict (confidence + status) instead of the live check count — the
   * sequence is the single objectives list, so it carries the report.
   */
  outcomes: ObjectiveResult[] | null
  activeObjective: string | null
  onSelect: (id: string) => void
}) {
  return (
    <div className="space-y-1 px-3 py-3">
      {objectives.map((objective, index) => {
        const stage = `objective_${objective.number}`
        // The report's verdict wins once it exists; the live stage/check map
        // is only authoritative while the session is still running.
        const outcome = outcomes?.find((o) => o.id === objective.id) ?? null
        const state: StageState = outcome ? outcome.status : stageStates[stage] ?? 'PENDING'
        const decided = objective.checks
          .map((c) => checkStatuses[c.id])
          .filter(Boolean) as ObjectiveCheckStatus[]
        const failed = decided.includes('FAIL')
        const allPass =
          decided.length === objective.checks.length && decided.every((s) => s === 'PASS')

        const resolved: StageState = outcome
          ? outcome.status
          : state === 'PASSED' || allPass
            ? 'PASSED'
            : state === 'FAILED' || failed
              ? 'FAILED'
              : state === 'RUNNING'
                ? 'RUNNING'
                : state === 'BLOCKED'
                  ? 'BLOCKED'
                  : state === 'NOT_VERIFIED'
                    ? 'NOT_VERIFIED'
                    : 'PENDING'

        const { Icon: StatusIcon, color } = STAGE_META[resolved] ?? STAGE_META.PENDING

        return (
          <div key={objective.id} className="relative">
            {index < objectives.length - 1 && (
              <span
                aria-hidden
                className="absolute left-[15px] top-[30px] bottom-[-4px] w-px"
                style={{ background: 'var(--as-border)' }}
              />
            )}
            <button
              type="button"
              onClick={() => onSelect(objective.id)}
              className="relative flex w-full items-start gap-3 rounded-lg px-2 py-2 text-left transition-all hover:bg-[color-mix(in_oklch,var(--as-accent)_6%,transparent)]"
              style={{
                background:
                  activeObjective === objective.id
                    ? 'color-mix(in oklch, var(--as-accent) 7%, transparent)'
                    : 'transparent',
                outline:
                  activeObjective === objective.id ? '1px solid var(--as-border-hi)' : 'none',
              }}
            >
              <span
                className="mt-0.5 flex h-[28px] w-[28px] shrink-0 items-center justify-center rounded-full border text-[11px] font-bold"
                style={{ borderColor: `color-mix(in oklch, ${color} 45%, transparent)`, color }}
              >
                {resolved === 'RUNNING' ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <StatusIcon size={13} />
                )}
              </span>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span
                    className="min-w-0 flex-1 text-[13px] font-semibold"
                    style={{ color: 'var(--as-text)' }}
                  >
                    {objective.number}. {objective.title}
                  </span>
                  {outcome ? (
                    <span className="flex shrink-0 flex-col items-end gap-[3px]">
                      <span className="mono text-[10.5px] leading-none" style={{ color }}>
                        {(outcome.confidence * 100).toFixed(0)}%
                      </span>
                      <span
                        className="inline-flex items-center rounded-full border px-1.5 py-[1px] text-[9.5px] font-semibold uppercase tracking-wider"
                        style={{
                          color,
                          borderColor: `color-mix(in oklch, ${color} 34%, transparent)`,
                        }}
                      >
                        {STAGE_META[resolved].label}
                      </span>
                    </span>
                  ) : (
                    <span className="mono ml-auto shrink-0 text-[10.5px]" style={{ color }}>
                      {decided.length}/{objective.checks.length}
                    </span>
                  )}
                </div>
                <p
                  className="mt-0.5 line-clamp-2 text-[11.5px] leading-snug"
                  style={{ color: 'var(--as-text-3)' }}
                >
                  {objective.statement}
                </p>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {objective.checks.map((c) => {
                    const s = checkStatuses[c.id]
                    const dotColor = s ? CHECK_META[s].color : 'var(--as-text-3)'
                    return (
                      <span
                        key={c.id}
                        title={s ? `${c.title}: ${CHECK_META[s].label}` : `${c.title}: pending`}
                        className="h-1.5 w-1.5 rounded-full"
                        style={{
                          background: s ? dotColor : 'transparent',
                          border: `1px solid ${dotColor}`,
                          opacity: s ? 1 : 0.5,
                        }}
                      />
                    )
                  })}
                </div>
              </div>
            </button>
          </div>
        )
      })}
    </div>
  )
}

// ── log console ──────────────────────────────────────────────────────────

interface LogLine {
  id: number
  at: string
  stage: string
  message: string
  tone: 'info' | 'ok' | 'warn' | 'error' | 'muted'
}

const LOG_TONE: Record<LogLine['tone'], string> = {
  info: 'var(--as-text-2)',
  ok: 'var(--as-verify)',
  warn: 'var(--as-warn)',
  error: 'var(--as-error)',
  muted: 'var(--as-text-3)',
}

function checkTone(status: ObjectiveCheckStatus): LogLine['tone'] {
  switch (status) {
    case 'PASS':
      return 'ok'
    case 'FAIL':
      return 'error'
    case 'NOT_VERIFIED':
      return 'warn'
    default:
      return 'muted'
  }
}

// ── console tracing ──────────────────────────────────────────────────────
//
// Every step of the Generate & Verify flow is echoed to the browser console
// under the `[G&V]` prefix. Filter the DevTools console by `G&V` to see the
// ordered trail: click -> workspace -> session -> SSE frames -> report.

function trace(...args: unknown[]): void {
  console.log('[G&V]', new Date().toISOString().slice(11, 23), ...args)
}

function traceError(...args: unknown[]): void {
  console.error('[G&V]', new Date().toISOString().slice(11, 23), ...args)
}

function LogConsole({ lines, connected }: { lines: LogLine[]; connected: boolean }) {
  const boxRef = useRef<HTMLDivElement>(null)

  // Scroll the console itself — never `scrollIntoView`, which walks up to the
  // app shell and shifts the whole page out of view (that hid the header and
  // left a dead strip at the bottom on every replayed frame).
  useEffect(() => {
    const box = boxRef.current
    if (box) box.scrollTop = box.scrollHeight
  }, [lines.length])

  // The log takes whatever the sequence leaves it.
  return (
    <div
      ref={boxRef}
      className={`mono ${lines.length > 0 ? 'flex-1' : 'flex-1 min-h-[40px]'} overflow-y-auto px-3 py-2 text-[11px] leading-relaxed`}
      style={{ background: 'var(--as-bg)' }}
    >
      {lines.length === 0 ? (
        <div style={{ color: 'var(--as-text-3)' }}>
          {connected
            ? 'Waiting for the first frame from the backend...'
            : 'Submit a problem above to start verification'}
        </div>
      ) : (
        lines.map((line) => (
          <div key={line.id} className="flex gap-2">
            <span className="shrink-0 opacity-70">{line.at}</span>
            <span className="shrink-0 opacity-70">[{line.stage}]</span>
            <span className="min-w-0 break-words" style={{ color: LOG_TONE[line.tone] }}>
              {line.message}
            </span>
          </div>
        ))
      )}
    </div>
  )
}

// ── main page ────────────────────────────────────────────────────────────

export function ObjectivesPage() {
  const [definitions, setDefinitions] = useState<ObjectiveDefinition[] | null>(null)
  const [stages, setStages] = useState<string[]>([])

  const [runId, setRunId] = useState<string | null>(null)
  // The prompt the on-screen session was started from. The minimised query
  // bar shows it as its placeholder, so the folded bar always reads as the
  // query that is running (or ran) instead of a blank hint.
  const [lastProblem, setLastProblem] = useState<string | null>(null)
  const [report, setReport] = useState<ObjectiveVerificationReport | null>(null)
  //: Experiment ID linked to this verification session (if any). Objective 4
  //: checks read facts from the linked experiment instead of this session's
  //: own empty experiment.
  const [linkedExperimentId, setLinkedExperimentId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [stageStates, setStageStates] = useState<Record<string, StageState>>({})
  const [checkStatuses, setCheckStatuses] = useState<Record<string, ObjectiveCheckStatus>>({})
  const [logs, setLogs] = useState<LogLine[]>([])
  const [activeObjective, setActiveObjective] = useState<string | null>(null)

  const [generatedFileNames, setGeneratedFileNames] = useState<string[]>([])
  const [codeGenerationStatus, setCodeGenerationStatus] = useState<'pending' | 'ok' | 'failed' | 'blocked'>('pending')
  const [codeGenerationMessage, setCodeGenerationMessage] = useState<string>('')
  // True once the objective/stage graph has been resolved (or failed) — the
  // session restore below waits for it so it can seed the timeline.
  const [workflowReady, setWorkflowReady] = useState(false)

  const unsubscribeRef = useRef<(() => void) | null>(null)
  const logSeq = useRef(0)
  //: Reconnect attempts for the SSE stream. Reset on each new session; capped
  //: so a permanently-broken stream doesn't retry forever.
  const reconnectRef = useRef({ count: 0, max: 4 })

  const pushLog = useCallback((stage: string, message: string, tone: LogLine['tone'] = 'info') => {
    setLogs((prev) => [
      ...prev.slice(-400),
      { id: logSeq.current++, at: stamp(new Date().toISOString()), stage, message, tone },
    ])
  }, [])

  const resetRun = useCallback(() => {
    setLogs([])
    setReport(null)
    setError(null)
    setCheckStatuses({})
    setStageStates({})
    setActiveObjective(null)
    setConnected(false)
    setGeneratedFileNames([])
    setCodeGenerationStatus('pending')
    setCodeGenerationMessage('')
    setLastProblem(null)
  }, [])

  // Load the fixed objective graph on mount.
  useEffect(() => {
    let cancelled = false
    void Promise.all([api.listObjectives(), api.objectiveStages()])
      .then(([defs, stageIds]) => {
        if (cancelled) return
        setDefinitions(defs)
        setStages(stageIds.stages)
        setWorkflowReady(true)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof ApiError ? err.message : 'Could not load the verification workflow')
        setWorkflowReady(true)
      })
    return () => {
      cancelled = true
      unsubscribeRef.current?.()
      unsubscribeRef.current = null
    }
  }, [])

  // ── SSE frame handling ─────────────────────────────────────────────────
  const applyFrame = useCallback(
    (update: ObjectiveStageUpdate) => {
      const stage = update.stage
      trace('SSE frame', { stage, status: update.status, objective_id: update.objective_id, message: update.message })
      if (update.check) {
        const { check } = update
        trace('check result', {
          stage,
          check_id: check.check_id,
          title: check.title,
          status: check.status,
          verification_level: check.verification_level,
          category: check.category,
        })
        setCheckStatuses((prev) => ({ ...prev, [check.check_id]: check.status }))
        pushLog(
          stage,
          `${check.title} -> ${CHECK_META[check.status].label}${check.actual ? ` — ${check.actual}` : ''}`,
          checkTone(check.status),
        )
      } else {
        pushLog(
          stage,
          update.message || STAGE_META[update.status]?.label || update.status,
          update.status === 'PASSED'
            ? 'ok'
            : update.status === 'FAILED'
              ? 'error'
              : update.status === 'BLOCKED' || update.status === 'NOT_VERIFIED'
                ? 'warn'
                : 'info',
        )
      }
      if (update.stage === 'code_generation' && update.payload) {
        const payload = update.payload || {}
        const files = (payload.generated_files as { name: string }[]) || []
        trace('code_generation payload', {
          status: payload.status,
          message: payload.message,
          file_count: files.length,
          file_names: files.map((f) => f.name),
        })
        setGeneratedFileNames(files.map((f) => f.name))
        // The backend reports "OK"/"FAILED"; normalise to the page's own set.
        const raw = String(payload.status || '').toUpperCase()
        setCodeGenerationStatus(raw === 'OK' ? 'ok' : raw ? 'failed' : 'pending')
        setCodeGenerationMessage(String(payload.message || update.message || ''))
      }
      if (update.status === 'RUNNING') {
        setStageStates((prev) => ({ ...prev, [stage]: 'RUNNING' }))
        if (update.objective_id) setActiveObjective(update.objective_id)
      } else {
        setStageStates((prev) => ({ ...prev, [stage]: update.status }))
      }
    },
    [pushLog],
  )

  const subscribe = useCallback(
    (id: string) => {
      unsubscribeRef.current?.()
      setConnected(true)
      trace('subscribing to SSE stream', { run_id: id })
      unsubscribeRef.current = api.streamObjectiveSession(id, {
        onOpen: () => {
          trace('SSE stream open', { run_id: id })
          setConnected(true)
        },
        onStage: applyFrame,
        onReport: (r) => {
          trace('final report received', {
            overall_status: r.overall_status,
            totals: r.totals,
            objectives: r.objectives?.map((o) => ({ id: o.id, status: o.status, confidence: o.confidence })),
          })
          setReport(r)
          setBusy(false)
          setConnected(false)
          setStageStates((prev) => ({ ...prev, report: 'PASSED' }))
          pushLog('report', `Verification complete — overall ${r.overall_status}`, 'ok')
        },
        onError: (message) => {
          traceError('stream error', { run_id: id, message })
          setError(message)
          setBusy(false)
          setConnected(false)
        },
        onEnd: () => {
          // Server closed the stream without delivering a report or error.
          // Attempt to reconnect a few times before falling back to polling.
          if (reconnectRef.current.count >= reconnectRef.current.max) {
            traceError('stream reconnect exhausted', { run_id: id })
            // Fall back to polling the session state API so the user still
            // gets a verdict even when SSE is unavailable.
            void (async () => {
              try {
                const state = await api.getObjectiveSession(id)
                setLinkedExperimentId(state.linked_experiment_id || null)
                if (state.report) {
                  setReport(state.report)
                  setBusy(false)
                  setConnected(false)
                  setStageStates((prev) => ({ ...prev, report: 'PASSED' }))
                  pushLog('report', `Verification complete — overall ${state.report.overall_status}`, 'ok')
                } else if (state.status === 'FAILED') {
                  setError(state.error || 'Verification failed')
                  setBusy(false)
                  setConnected(false)
                } else {
                  setError('Verification stream ended before a verdict arrived')
                  setBusy(false)
                  setConnected(false)
                }
              } catch (err) {
                setError('Verification stream ended and session state could not be read')
                setBusy(false)
                setConnected(false)
              }
            })()
            return
          }
          reconnectRef.current.count += 1
          trace('stream ended, reconnecting', {
            run_id: id,
            attempt: reconnectRef.current.count,
          })
          pushLog(
            'client',
            `Stream ended — reconnecting (attempt ${reconnectRef.current.count}/${reconnectRef.current.max})`,
            'warn',
          )
          setTimeout(() => subscribe(id), 1000)
        },
      })
    },
    [applyFrame, pushLog],
  )

  // ── restore the current session on (re)mount ──────────────────────────────
  //
  // Navigating to another page unmounts this one, so everything is rebuilt
  // from the backend session record when the user comes back: frames replay
  // through the same handler as live SSE, and a run that is still going is
  // simply re-attached. The session lives until the user submits a new
  // problem (or presses New) — tab switches never end it.
  const restoredRef = useRef(false)

  useEffect(() => {
    if (restoredRef.current || !workflowReady) return
    restoredRef.current = true

    const prior = recallObjectiveRun()
    if (!prior) return

    // Cancel-safe: navigating away mid-restore must not touch state, open an
    // SSE connection nobody will close, or clear the pointer — and the next
    // mount has to be able to try again.
    let cancelled = false
    let finished = false

    void (async () => {
      try {
        const state = await api.getObjectiveSession(prior)
        if (cancelled) return
        trace('restoring session from backend record', {
          run_id: prior,
          status: state.status,
          running: state.running,
          updates: state.updates?.length ?? 0,
        })
        setRunId(prior)
        setLastProblem(state.problem_statement || null)
        setLinkedExperimentId(state.linked_experiment_id || null)

        if (state.running) {
          // Still running: the stream replays every stored frame itself, so
          // attaching is enough — replaying here too would double the log.
          setStageStates(Object.fromEntries(stages.map((s) => [s, 'PENDING' as StageState])))
          setBusy(true)
          pushLog('client', `Reattached to session ${prior.slice(0, 8)}`, 'ok')
          // Fresh attachment: reset the reconnect budget for this session.
          reconnectRef.current = { count: 0, max: 4 }
          subscribe(prior)
          return
        }

        for (const update of state.updates ?? []) applyFrame(update)
        if (state.report) {
          setReport(state.report)
          setStageStates((prev) => ({ ...prev, report: 'PASSED' }))
          pushLog('report', `Verification complete — overall ${state.report.overall_status}`, 'ok')
        }
        if (state.error) {
          setError(state.error)
          pushLog('client', state.error, 'error')
        }
        setConnected(false)
        setBusy(false)
      } catch (err) {
        if (cancelled) return
        // The pointer names a session the backend no longer knows: clear it
        // so the page falls back to the empty input instead of a dead run.
        forgetObjectiveRun()
        traceError('session restore failed', { run_id: prior, error: err })
      } finally {
        finished = true
      }
    })()

    return () => {
      cancelled = true
      if (!finished) restoredRef.current = false
    }
  }, [workflowReady, stages, applyFrame, subscribe, pushLog])

  // ── start verification ──────────────────────────────────────────────────
  const startVerification = useCallback(
    async (problem: string) => {
      trace('▶ Generate & Verify clicked', { problem })
      resetRun()
      setBusy(true)
      setLastProblem(problem)
      pushLog('client', `Starting verification for: "${problem.slice(0, 80)}..."`)

      // Auto-resolve workspace — the user should not need to select one.
      let workspaceId: string
      try {
        const list = await api.listWorkspaces(1, 1)
        if (list.items.length > 0) {
          workspaceId = list.items[0].id
          trace('workspace resolved (existing)', { workspace_id: workspaceId, name: list.items[0].name })
        } else {
          trace('no workspace found — creating "Default Workspace"')
          const created = await api.createWorkspace({ name: 'Default Workspace' })
          workspaceId = created.id
          trace('workspace created', { workspace_id: workspaceId, name: created.name })
        }
      } catch (err) {
        const message = err instanceof ApiError ? err.message : 'Could not resolve workspace'
        traceError('workspace resolution failed', { message, error: err })
        setError(message)
        setBusy(false)
        pushLog('client', message, 'error')
        return
      }

      const payload: FreshSessionCreate = {
        workspace_id: workspaceId,
        problem_statement: problem,
      }

      let accepted
      try {
        trace('POST /objective-verification/sessions', payload)
        accepted = await api.createObjectiveSession(payload)
        trace('session accepted', accepted)
      } catch (err) {
        const message = err instanceof ApiError ? err.message : 'Could not start verification'
        traceError('session creation failed', { status: err instanceof ApiError ? err.status : undefined, message, error: err })
        setError(message)
        setBusy(false)
        pushLog('client', message, 'error')
        return
      }

      setRunId(accepted.run_id)
      setLinkedExperimentId(null)
      rememberObjectiveRun(accepted.run_id)
      // Fresh session: reset the reconnect budget so a new run always gets
      // up to `max` reconnection attempts before falling back to polling.
      reconnectRef.current = { count: 0, max: 4 }
      setStageStates(Object.fromEntries(stages.map((s) => [s, 'PENDING' as StageState])))
      pushLog('client', `Session ${accepted.run_id.slice(0, 8)} created — subscribing`, 'ok')

      subscribe(accepted.run_id)

      // Same problem, sibling view: design the project's pipeline too, so the
      // Pipeline page already has it when the user opens it. Purely additive —
      // a planner failure must never stop the verification itself.
      void api
        .generatePipelinePlan({ description: problem })
        .then((plan) => {
          setPipelinePlanDraft({ description: problem, plan, runId: accepted.run_id })
          trace('pipeline plan generated for the Pipeline page', {
            run_id: accepted.run_id,
            stages: plan.stages.length,
          })
          pushLog(
            'pipeline',
            `Plan ready — ${plan.stages.length} stages waiting on the Pipeline page`,
            'ok',
          )
        })
        .catch((err: unknown) => {
          const message = err instanceof ApiError ? err.message : 'planner unavailable'
          traceError('pipeline plan generation failed', { message, error: err })
          pushLog('pipeline', `Pipeline plan skipped — ${message}`, 'warn')
        })
    },
    [resetRun, stages, pushLog, subscribe],
  )

  // ── start over ─────────────────────────────────────────────────────────
  const startFresh = useCallback(() => {
    unsubscribeRef.current?.()
    unsubscribeRef.current = null
    resetRun()
    setRunId(null)
    setLinkedExperimentId(null)
    forgetObjectiveRun()
  }, [resetRun])

  // ── derived ────────────────────────────────────────────────────────────
  const totals = useMemo(() => {
    const out: Record<string, number> = { PASS: 0, FAIL: 0, NOT_VERIFIED: 0, BLOCKED: 0 }
    if (report) {
      for (const key of Object.keys(out)) out[key] = report.totals?.[key] ?? 0
    } else {
      for (const status of Object.values(checkStatuses)) {
        if (out[status] !== undefined) out[status] += 1
      }
    }
    return out
  }, [report, checkStatuses])

  const activeDefinition = useMemo(
    () => definitions?.find((o) => o.id === activeObjective) ?? null,
    [definitions, activeObjective],
  )
  const activeResult = useMemo(
    () => report?.objectives.find((o) => o.id === activeObjective) ?? null,
    [report, activeObjective],
  )

  const graphLoading = definitions === null

  return (
    <div className="flex h-full min-w-0 flex-col" style={{ background: 'var(--as-bg)' }}>
      <PageHeader
        dense
        title="Objective Verification"
        subtitle="Audit how the ML pipeline is designed and why each decision was made. No dataset or training required."
        right={
          <div className="flex items-center gap-2">
            {connected && (
              <span
                className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium"
                style={{ borderColor: 'var(--as-border-hi)', color: 'var(--as-teal)' }}
              >
                <Radio size={10} className="animate-pulse" /> streaming
              </span>
            )}
            {runId && (
              <button
                onClick={startFresh}
                className="flex h-[28px] items-center gap-1.5 rounded-sm border px-2.5 text-[13px] transition"
                style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-2)' }}
              >
                <RotateCw size={13} /> New
              </button>
            )}
          </div>
        }
      />

      {/* ── session bar (kept while a run is open) ──────────────────────── */}
      {runId && (
        <div
          className="flex items-center gap-3 border-b px-5 py-3"
          style={{ borderColor: 'var(--as-border)' }}
        >
          <FlaskConical size={15} style={{ color: 'var(--as-accent)' }} />
          <div className="min-w-0 flex-1">
            <div className="text-[13px] font-medium" style={{ color: 'var(--as-text)' }}>
              Session <span className="mono">{runId.slice(0, 8)}</span>
            </div>
            {report && (
              <div className="mt-0.5 truncate text-[12px]" style={{ color: 'var(--as-text-3)' }}>
                {report.problem_statement}
              </div>
            )}
          </div>
          {/* Navigation to the sibling pages, keyed by this session's run id. */}
          <div className="flex shrink-0 items-center gap-2">
            <Link
              to={`/sandbox?run=${encodeURIComponent(runId)}`}
              className="flex h-[28px] items-center gap-1.5 rounded-md border px-2.5 text-[12px] font-medium transition-all hover:shadow-[0_0_12px_var(--as-accent-glow)]"
              style={{
                borderColor: 'color-mix(in oklch, var(--as-accent) 40%, transparent)',
                color: 'var(--as-accent-hi)',
              }}
              title="View the generated code for this session"
            >
              <Code2 size={12} /> Sandbox
            </Link>
            <Link
              to="/pipeline"
              className="flex h-[28px] items-center gap-1.5 rounded-md border px-2.5 text-[12px] font-medium transition-all hover:shadow-[0_0_12px_var(--as-accent-glow)]"
              style={{
                borderColor: 'color-mix(in oklch, var(--as-violet, #8b5cf6) 40%, transparent)',
                color: 'var(--as-violet, #8b5cf6)',
              }}
              title="Open the pipeline generated for this session"
            >
              <GitBranch size={12} /> Pipeline
            </Link>
            <Link
              to={`/evidence?run=${encodeURIComponent(runId)}`}
              className="flex h-[28px] items-center gap-1.5 rounded-md border px-2.5 text-[12px] font-medium transition-all hover:shadow-[0_0_12px_var(--as-accent-glow)]"
              style={{
                borderColor: 'color-mix(in oklch, var(--as-teal) 40%, transparent)',
                color: 'var(--as-teal)',
              }}
              title="Inspect the recorded design decisions and evidence"
            >
                  <ShieldCheck size={12} /> Evidence
            </Link>
          </div>
        </div>
      )}

      {/* ── input ──────────────────────────────────────────────────────── */}
      {/* Always available: the session above survives every tab switch, and a
          new query submitted here is what starts a new session. */}
      <ProblemInput
        onSubmit={(p) => void startVerification(p)}
        busy={busy}
        compact={Boolean(runId) || busy}
        prompt={lastProblem || report?.problem_statement || null}
        hint={
          runId
            ? 'A new query starts a new session and replaces the one above.'
            : undefined
        }
      />

      {/* ── error banner ───────────────────────────────────────────────── */}
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
              Verification error
            </div>
            <div className="text-[12.5px]" style={{ color: 'var(--as-text-2)' }}>
              {error}
            </div>
          </div>
        </div>
      )}

      {/* ── body ───────────────────────────────────────────────────────── */}
      {/* Two columns on top (sequence | summary) and a full-width Backend Log
          row underneath. The sequence is the single objectives list — it owns
          the final verdicts and the evidence entry point — so the log reads
          across the whole page instead of a 360px strip.
          The top row is sized by the sequence's own content: the summary
          panel is taken out of flow on lg (below), so the log starts exactly
          where the sequence ends and takes every leftover pixel — no dead
          space above it. fit-content caps that row so the log keeps at least
          ~190px, scrolling the sequence internally on short viewports. */}
      <div
        className="grid min-h-0 flex-1 gap-px lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)] lg:grid-rows-[fit-content(calc(100%_-_190px))_minmax(0,1fr)]"
        style={{ background: 'var(--as-border)' }}
      >
        {/* top-left: verification sequence (carries the report verdicts) */}
        <div className="flex min-h-0 flex-col" style={{ background: 'var(--as-bg-2)' }}>
          <SectionTitle
            right={
              report ? (
                <Link
                  to={`/evidence?run=${encodeURIComponent(report.run_id)}`}
                  className="flex h-[22px] shrink-0 items-center gap-1.5 rounded-md px-2 text-[11px] font-medium transition-all hover:shadow-[0_0_12px_var(--as-teal)]"
                  style={{
                    background: 'color-mix(in oklch, var(--as-teal) 12%, transparent)',
                    color: 'var(--as-teal)',
                  }}
                  title="Inspect the recorded design decisions, evidence and per-check results"
                >
                  <ExternalLink size={11} /> Open full evidence
                </Link>
              ) : null
            }
          >
            Verification Sequence
          </SectionTitle>
          {/* The grid row bounds this cell, so the sequence scrolls only when
              it genuinely exceeds the space — it still shrinks before it could
              spill past the app shell and leave a dead strip below. */}
          <div className="min-h-0 flex-1 overflow-y-auto">
            {graphLoading ? (
              <div className="space-y-2 px-3 py-3">
                {[0, 1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="h-[58px] animate-pulse rounded-lg"
                    style={{ background: 'var(--as-bg-3)' }}
                  />
                ))}
              </div>
            ) : (
              <WorkflowTimeline
                objectives={definitions}
                stageStates={stageStates}
                checkStatuses={checkStatuses}
                outcomes={report?.objectives ?? null}
                activeObjective={activeObjective}
                onSelect={setActiveObjective}
              />
            )}
          </div>
        </div>

        {/* right: progress summary + final verdict, held in a relative shim.
            On lg the panel is taken out of flow, so its length never dictates
            the top row's height — the sequence does — and the grid gives
            every leftover pixel to the log below. The panel still fills the
            row (inset-0) and scrolls its own overflow. */}
        <div className="relative min-h-0" style={{ background: 'var(--as-bg)' }}>
          <div
            className="flex min-h-0 flex-col overflow-y-auto lg:absolute lg:inset-0"
            style={{ background: 'var(--as-bg)' }}
          >
          {!report && !busy && !runId && (
            <EmptyState
              icon={<ShieldCheck size={19} />}
              title="No verification session yet"
              detail="Describe an ML problem above. The system will generate pipeline code and verify the four objectives — no dataset or training required."
            />
          )}

          {!report && busy && !activeDefinition && (
            <EmptyState
              icon={<Loader2 size={19} className="animate-spin" />}
              title="Starting verification..."
              detail="Waiting on real backend progress. Each verdict appears as its check completes; nothing here is simulated."
            />
          )}

          {/* restored session that stopped before the final report */}
          {!report && !busy && runId && !activeDefinition && (
            <EmptyState
              icon={<CircleSlash size={19} />}
              title={`Session ${runId.slice(0, 8)} ended without a report`}
              detail="It stopped before the final verdict. Submit a new query above to start a new session."
            />
          )}

          {/* active objective: the selected objective's verdict with its checks
              in detail — status, confidence, evidence kind, expected/actual.
              On lg the section stretches to exactly the height of the
              Verification Sequence panel, so both panels end on the same
              line; the check list scrolls inside it if it needs more room. */}
          {activeDefinition && (
            <section
              className="flex flex-col border-b lg:h-full lg:min-h-0 lg:shrink-0"
              style={{ borderColor: 'var(--as-border)' }}
            >
              <SectionTitle
                right={
                  activeResult ? (
                    <div className="flex items-center gap-2">
                      <span className="mono text-[11px]" style={{ color: 'var(--as-text-3)' }}>
                        {(activeResult.confidence * 100).toFixed(0)}%
                      </span>
                      <span
                        className="inline-flex items-center gap-1 rounded-full border px-1.5 py-[1px] text-[9.5px] font-semibold uppercase tracking-wider"
                        style={{
                          color: STAGE_META[activeResult.status].color,
                          borderColor: `color-mix(in oklch, ${STAGE_META[activeResult.status].color} 34%, transparent)`,
                        }}
                      >
                        {STAGE_META[activeResult.status].label}
                      </span>
                    </div>
                  ) : busy ? (
                    <span
                      className="inline-flex items-center gap-1 text-[11px]"
                      style={{ color: 'var(--as-accent)' }}
                    >
                      <Loader2 size={10} className="animate-spin" /> running
                    </span>
                  ) : (
                    <span className="text-[11px]" style={{ color: 'var(--as-text-3)' }}>
                      no verdict
                    </span>
                  )
                }
              >
                <span className="inline-flex items-center gap-2">
                  <FlaskConical size={12} />
                  Objective {activeDefinition.number} — {activeDefinition.title}
                </span>
              </SectionTitle>
              <p
                className="line-clamp-2 px-4 pb-1 pt-2 text-[12px] leading-relaxed"
                style={{ color: 'var(--as-text-3)' }}
                title={activeDefinition.statement}
              >
                {activeDefinition.statement}
              </p>
              <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto px-4 py-3">
                {activeResult
                  ? activeResult.checks.map((check) => {
                      const meta = CHECK_META[check.status]
                      return (
                        <div
                          key={check.check_id}
                          className="rounded-lg border px-3 py-2"
                          style={{
                            borderColor: 'var(--as-border)',
                            background: 'var(--as-bg-2)',
                          }}
                        >
                          <div className="flex items-center gap-2">
                            <meta.Icon
                              size={12}
                              className="shrink-0"
                              style={{ color: meta.color }}
                            />
                            <span
                              className="min-w-0 flex-1 truncate text-[12px] font-medium"
                              style={{ color: 'var(--as-text)' }}
                              title={check.title}
                            >
                              {check.title}
                            </span>
                            <CategoryTag category={check.category} />
                            <span
                              className="mono shrink-0 text-[10.5px]"
                              style={{ color: 'var(--as-text-3)' }}
                              title="check confidence"
                            >
                              {(check.confidence * 100).toFixed(0)}%
                            </span>
                            <CheckPill status={check.status} small />
                          </div>
                          {(check.expected || check.actual) && (
                            <div className="mt-1.5 grid gap-x-4 gap-y-1 sm:grid-cols-2">
                              {check.expected && (
                                <p
                                  className="line-clamp-2 min-w-0 text-[11.5px] leading-snug"
                                  style={{ color: 'var(--as-text-2)' }}
                                  title={check.expected}
                                >
                                  <span className="label-xs mr-1" style={{ color: 'var(--as-text-3)' }}>
                                    Expected
                                  </span>
                                  {check.expected}
                                </p>
                              )}
                              {check.actual && (
                                <p
                                  className="line-clamp-2 min-w-0 text-[11.5px] leading-snug"
                                  style={{ color: meta.color }}
                                  title={check.actual}
                                >
                                  <span className="label-xs mr-1" style={{ color: 'var(--as-text-3)' }}>
                                    Actual
                                  </span>
                                  {check.actual}
                                </p>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })
                  : activeDefinition.checks.map((check) => {
                      const status = checkStatuses[check.id]
                      const meta = status ? CHECK_META[status] : null
                      return (
                        <div
                          key={check.id}
                          className="rounded-lg border px-3 py-2"
                          style={{
                            borderColor: 'var(--as-border)',
                            background: 'var(--as-bg-2)',
                          }}
                        >
                          <div className="flex items-center gap-2">
                            {meta ? (
                              <meta.Icon
                                size={12}
                                className="shrink-0"
                                style={{ color: meta.color }}
                              />
                            ) : (
                              <span
                                className="h-[9px] w-[9px] shrink-0 rounded-full"
                                style={{ border: '1px solid var(--as-text-3)', opacity: 0.5 }}
                              />
                            )}
                            <span
                              className="min-w-0 flex-1 truncate text-[12px] font-medium"
                              style={{ color: 'var(--as-text)' }}
                              title={check.title}
                            >
                              {check.title}
                            </span>
                            {status ? (
                              <CheckPill status={status} small />
                            ) : (
                              <span
                                className="mono text-[9.5px] uppercase tracking-wider"
                                style={{ color: 'var(--as-text-3)' }}
                              >
                                pending
                              </span>
                            )}
                          </div>
                          <div className="mt-1.5 grid gap-x-4 gap-y-1 sm:grid-cols-2">
                            <p
                              className="line-clamp-2 min-w-0 text-[11.5px] leading-snug"
                              style={{ color: 'var(--as-text-2)' }}
                              title={check.expected}
                            >
                              <span className="label-xs mr-1" style={{ color: 'var(--as-text-3)' }}>
                                Expected
                              </span>
                              {check.expected}
                            </p>
                            <p
                              className="mono line-clamp-2 min-w-0 text-[11.5px] leading-snug"
                              style={{ color: 'var(--as-text-3)' }}
                              title={check.evidence_source}
                            >
                              <span className="label-xs mr-1">Evidence</span>
                              {check.evidence_source}
                            </p>
                          </div>
                        </div>
                      )
                    })}
              </div>
            </section>
          )}

          {/* generated code summary — the code itself lives in the Sandbox */}
          {codeGenerationStatus === 'ok' && generatedFileNames.length > 0 && runId && (
            <section className="border-b" style={{ borderColor: 'var(--as-border)' }}>
              <SectionTitle
                right={
                  <Link
                    to={`/sandbox?run=${encodeURIComponent(runId)}`}
                    className="flex h-[26px] items-center gap-1.5 rounded-md px-2.5 text-[12px] font-medium transition-all hover:shadow-[0_0_12px_var(--as-accent-glow)]"
                    style={{
                      background: 'color-mix(in oklch, var(--as-accent) 16%, transparent)',
                      color: 'var(--as-accent-hi)',
                    }}
                  >
                    <ExternalLink size={12} /> Open in Sandbox
                  </Link>
                }
              >
                <span className="inline-flex items-center gap-1.5">
                  <Code2 size={12} /> Generated Code
                </span>
              </SectionTitle>
              <div className="px-4 py-3">
                <div className="flex flex-wrap gap-2">
                  {generatedFileNames.map((name) => (
                    <span
                      key={name}
                      className="mono inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11.5px]"
                      style={{
                        borderColor: 'var(--as-border-hi)',
                        background: 'var(--as-bg-2)',
                        color: 'var(--as-teal)',
                      }}
                    >
                      <Code2 size={11} />
                      {name}
                    </span>
                  ))}
                </div>
                <p className="mt-2 text-[11.5px]" style={{ color: 'var(--as-text-3)' }}>
                  {generatedFileNames.length} file(s) generated for this session. Open in
                  Sandbox to view, edit, or copy. The generated files themselves are never
                  run — edit one there to execute your own version.
                </p>
                {codeGenerationMessage && (
                  <p className="mt-1 text-[11.5px] leading-relaxed" style={{ color: 'var(--as-text-3)' }}>
                    {codeGenerationMessage}
                  </p>
                )}
              </div>
            </section>
          )}

          {/* a real error when the provider could not generate — never faked */}
          {codeGenerationStatus === 'failed' && (
            <div
              className="flex items-start gap-2 border-b px-5 py-2.5"
              style={{
                borderColor: 'var(--as-border)',
                background: 'color-mix(in oklch, var(--as-error) 8%, transparent)',
              }}
            >
              <AlertTriangle size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--as-error)' }} />
              <div className="min-w-0 text-[12px] leading-relaxed" style={{ color: 'var(--as-text-2)' }}>
                <span className="label-xs mr-1.5" style={{ color: 'var(--as-error)' }}>
                  Code generation failed
                </span>
                {codeGenerationMessage ||
                  'The configured LLM provider did not return usable code. Nothing was substituted.'}
              </div>
            </div>
          )}

          {/* final audit report — summary only; details are in Evidence */}
          {report && (
            <>
              <div
                className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b px-5 py-3"
                style={{ borderColor: 'var(--as-border)' }}
              >
                <div>
                  <div className="label-xs" style={{ color: 'var(--as-text-3)' }}>
                    Final Verdict
                  </div>
                  <div className="mt-0.5">
                    <span
                      className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider"
                      style={{
                        color: STAGE_META[report.overall_status].color,
                        background: `color-mix(in oklch, ${STAGE_META[report.overall_status].color} 14%, transparent)`,
                        borderColor: `color-mix(in oklch, ${STAGE_META[report.overall_status].color} 34%, transparent)`,
                      }}
                    >
                      {STAGE_META[report.overall_status].label}
                    </span>
                  </div>
                </div>
                <div>
                  <div className="label-xs" style={{ color: 'var(--as-text-3)' }}>
                    Confidence
                  </div>
                  <div className="mono mt-0.5 text-[13px]" style={{ color: 'var(--as-text)' }}>
                    {(report.overall_confidence * 100).toFixed(0)}%
                  </div>
                </div>
                {(['PASS', 'FAIL', 'NOT_VERIFIED', 'BLOCKED'] as const).map((s) => (
                  <div key={s}>
                    <div className="label-xs" style={{ color: 'var(--as-text-3)' }}>
                      {s === 'NOT_VERIFIED' ? 'not verified' : s.toLowerCase()}
                    </div>
                    <div className="mono mt-0.5 text-[13px]" style={{ color: CHECK_META[s].color }}>
                      {totals[s] ?? 0}
                    </div>
                  </div>
                ))}
                <div className="mono ml-auto text-[11.5px]" style={{ color: 'var(--as-text-3)' }}>
                  {stamp(report.started_at)}-{stamp(report.completed_at)}
                </div>
              </div>

              {/* Evidence mix: what kind of proof backs this verdict */}
              {(report.evidence_categories ?? Object.keys(report.verification_levels ?? {}).length > 0) && (
                <div
                  className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b px-5 py-2"
                  style={{ borderColor: 'var(--as-border)' }}
                >
                  <span className="label-xs" style={{ color: 'var(--as-text-3)' }}>
                    Evidence mix
                  </span>
                  {Object.entries(report.evidence_categories ?? {}).map(([cat, n]) => {
                    const meta = CATEGORY_META[cat]
                    if (!meta) return null
                    return (
                      <span key={cat} className="flex items-baseline gap-1.5 text-[11.5px]">
                        <span className="mono" style={{ color: 'var(--as-teal)' }}>
                          {n}
                        </span>
                        <span style={{ color: 'var(--as-text-3)' }} title={meta.hint}>
                          {meta.label}
                        </span>
                      </span>
                    )
                  })}
                  <span className="ml-auto text-[11px] italic" style={{ color: 'var(--as-text-3)' }}>
                    A repository-level pass confirms a capability exists in source — it does not
                    prove a specific generated decision is correct.
                  </span>
                </div>
              )}

              {report.overall_status !== 'PASSED' && (
                <div
                  className="flex items-start gap-2 border-b px-5 py-2.5"
                  style={{
                    borderColor: 'var(--as-border)',
                    background: 'color-mix(in oklch, var(--as-warn) 8%, transparent)',
                  }}
                >
                  <CircleSlash size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--as-warn)' }} />
                  <p className="text-[12px] leading-relaxed" style={{ color: 'var(--as-text-2)' }}>
                    {report.overall_status === 'FAILED'
                      ? 'At least one objective failed. Open the Evidence page for the failing checks and what was actually observed.'
                      : report.overall_status === 'NOT_VERIFIED'
                        ? 'A design-time audit produces no training run, so checks that depend on metrics, decisions, evidence or artifacts report NOT VERIFIED rather than PASS. Source-level checks (pipeline structure, agent separation, tool registry) are genuinely verified.'
                        : 'A prerequisite stage prevented verification. Check the log for details.'}
                  </p>
                </div>
              )}

              {/* The per-objective verdicts live in the Verification Sequence
                  now — no duplicate list here. Every sequence row carries the
                  number, confidence and status, and the sequence header owns
                  the "Open full evidence" action. */}
            </>
          )}
          </div>
        </div>

        {/* bottom: backend log — spans the full page width under both columns */}
        <div
          className="flex max-h-[240px] min-h-0 flex-col lg:col-span-2 lg:max-h-none"
          style={{ background: 'var(--as-bg-2)' }}
        >
          <SectionTitle
            right={
              logs.length > 0 ? (
                <span className="mono text-[11px]" style={{ color: 'var(--as-text-3)' }}>
                  {logs.length} frames
                </span>
              ) : null
            }
          >
            <span className="inline-flex items-center gap-1.5">
              <Terminal size={11} /> Backend Log
            </span>
          </SectionTitle>
          <LogConsole lines={logs} connected={busy} />
        </div>
      </div>
    </div>
  )
}
