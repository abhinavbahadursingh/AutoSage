/**
 * AutoSage Sandbox — Code Workspace for a Verification Session.
 *
 * Displays the LLM-generated pipeline implementation (pipeline, training /
 * evaluation script, configuration, documentation) for one objective
 * verification session, identified by its run id:
 *
 *   /sandbox?run=<run_id>   — a specific session
 *   /sandbox                — falls back to the most recent run pointer
 *
 * The files come from the backend session record (GET /sessions/{run_id}),
 * which persists them — not from a page-local cache. If the session is still
 * running, the page follows the SSE stream so the files appear as soon as
 * code generation completes.
 *
 * Generated output itself is never executed: Run unlocks only for a Python
 * file the user has created or edited, and only against an available Docker
 * sandbox — the editor says so explicitly either way.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Code2,
  FileCode,
  FlaskConical,
  Loader2,
  Radio,
  ShieldCheck,
  ShieldAlert,
} from 'lucide-react'

import {
  api,
  ApiError,
  type ObjectiveDesignRecord,
} from '../lib/api'
import { EmptyState } from '../components/ui/Primitives'
import { PageHeader } from '../components/layout/Sidebar'
import { SandboxIDE, type ExternalFile } from '../components/workspace/SandboxIDE'
import { recallObjectiveRun } from '../lib/objectiveRun'

type GenStatus = 'pending' | 'ok' | 'failed'

export function SandboxPage() {
  const [searchParams] = useSearchParams()
  const runIdParam = searchParams.get('run')
  const runId = runIdParam || recallObjectiveRun()

  const [loading, setLoading] = useState(!!runId)
  const [error, setError] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)

  const [files, setFiles] = useState<ExternalFile[]>([])
  const [genStatus, setGenStatus] = useState<GenStatus>('pending')
  const [genMessage, setGenMessage] = useState<string>('')
  const [problem, setProblem] = useState<string>('')
  const [sessionStatus, setSessionStatus] = useState<string>('PENDING')
  const [design, setDesign] = useState<ObjectiveDesignRecord | null>(null)

  const unsubscribeRef = useRef<(() => void) | null>(null)

  const applyCodegenPayload = useCallback(
    (payload: Record<string, unknown> | null | undefined, fallbackMessage?: string) => {
      if (!payload) return
      const next = (payload.generated_files as ExternalFile[] | undefined) ?? []
      if (next.length > 0) setFiles(next)
      const raw = String(payload.status || '').toUpperCase()
      if (raw) setGenStatus(raw === 'OK' ? 'ok' : 'failed')
      const message = String(payload.message || fallbackMessage || '')
      if (message) setGenMessage(message)
      const designRecord = payload.design as ObjectiveDesignRecord | undefined
      if (designRecord) setDesign((prev) => ({ ...(prev ?? {}), ...designRecord }))
    },
    [],
  )

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
        setSessionStatus(state.status)
        setFiles(state.generated_files ?? [])
        setDesign(state.design ?? state.report?.design ?? null)
        const rawGen = String(state.code_generation_status || '').toUpperCase()
        if (state.generated_files && state.generated_files.length > 0) {
          setGenStatus('ok')
        } else if (rawGen) {
          setGenStatus(rawGen === 'OK' ? 'ok' : 'failed')
        }
        if (state.code_generation_message) setGenMessage(state.code_generation_message)
        if (state.error) setError(state.error)

        // A still-running session streams its files in; follow it.
        if (state.running) subscribe()
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
  const subscribe = useCallback(() => {
    if (!runId || unsubscribeRef.current) return
    setConnected(true)
    unsubscribeRef.current = api.streamObjectiveSession(runId, {
      onOpen: () => setConnected(true),
      onStage: (update) => {
        if (update.stage === 'code_generation') {
          applyCodegenPayload(update.payload, update.message)
        }
        if (update.stage === 'input' && update.message) setProblem((p) => p || update.message)
      },
      onReport: (report) => {
        if (report.code_generation_status) {
          setGenStatus(
            String(report.code_generation_status).toUpperCase() === 'OK' ? 'ok' : 'failed',
          )
        }
        if (report.code_generation_message) setGenMessage(report.code_generation_message)
        if (report.design) setDesign(report.design)
        setSessionStatus('COMPLETED')
        setConnected(false)
      },
      onError: (message) => {
        setError(message)
        setConnected(false)
      },
    })
  }, [runId, applyCodegenPayload])

  useEffect(() => {
    document.title = 'Sandbox | AutoSage'
  }, [])

  // ── no run selected ────────────────────────────────────────────────────
  if (!runId) {
    return (
      <div className="flex h-full min-w-0 flex-col" style={{ background: 'var(--as-bg)' }}>
        <PageHeader
          title="Sandbox"
          subtitle="Code workspace for a verification session's generated pipeline."
        />
        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <EmptyState
            icon={<Code2 size={19} />}
            title="No verification session selected"
            detail="Start a verification on the Objectives page — its generated code appears here, scoped to that session's run id."
          />
          <div className="mt-4 flex justify-center">
            <Link
              to="/objectives"
              className="flex h-[30px] items-center gap-1.5 rounded-md border px-3 text-[12.5px] font-medium transition-all hover:shadow-[0_0_12px_var(--as-accent-glow)]"
              style={{
                borderColor: 'color-mix(in oklch, var(--as-accent) 40%, transparent)',
                color: 'var(--as-accent-hi)',
              }}
            >
              <FlaskConical size={12} /> Go to Objectives
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-w-0 flex-col" style={{ background: 'var(--as-bg)' }}>
      <PageHeader
        title="Sandbox"
        subtitle={
          files.length > 0
            ? `${files.length} generated file(s) for this session. Run your own edited copy in the Docker sandbox.`
            : 'The generated pipeline code for one verification session. Generated files are never executed — edit one to run your own version.'
        }
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
              className="mono rounded border px-2 py-0.5 text-[11px]"
              style={{ borderColor: 'var(--as-border-hi)', color: 'var(--as-text-3)' }}
              title="These files belong to this verification session"
            >
              run {runId.slice(0, 8)}
            </span>
            <Link
              to="/objectives"
              className="flex h-[28px] items-center gap-1.5 rounded-sm border px-2.5 text-[13px] transition"
              style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-2)' }}
            >
              <FlaskConical size={13} /> Objectives
            </Link>
            <Link
              to={`/evidence?run=${encodeURIComponent(runId)}`}
              className="flex h-[28px] items-center gap-1.5 rounded-sm border px-2.5 text-[13px] transition"
              style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-2)' }}
              title="Inspect the recorded design decisions and evidence"
            >
              <ShieldCheck size={13} /> Evidence
            </Link>
          </div>
        }
      />

      {/* session context strip */}
      <div
        className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b px-5 py-2"
        style={{ borderColor: 'var(--as-border)' }}
      >
        <span className="mono text-[11.5px]" style={{ color: 'var(--as-text-3)' }}>
          session {runId.slice(0, 8)} · {sessionStatus.toLowerCase()}
        </span>
        {problem && (
          <span className="min-w-0 flex-1 truncate text-[12px]" style={{ color: 'var(--as-text-2)' }}>
            {problem}
          </span>
        )}
        {design?.algorithm && (
          <span className="mono text-[11.5px]" style={{ color: 'var(--as-teal)' }}>
            {design.algorithm}
          </span>
        )}
      </div>

      {/* session load error — e.g. run id not found on the backend */}
      {error && (
        <div
          className="flex items-start gap-2 border-b px-5 py-2.5"
          style={{
            borderColor: 'var(--as-border)',
            background: 'color-mix(in oklch, var(--as-error) 10%, transparent)',
          }}
          role="alert"
        >
          <ShieldAlert size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--as-error)' }} />
          <div className="min-w-0 flex-1">
            <div className="text-[13px] font-medium" style={{ color: 'var(--as-error)' }}>
              Could not load this session
            </div>
            <div className="text-[12.5px]" style={{ color: 'var(--as-text-2)' }}>
              {error}
            </div>
          </div>
        </div>
      )}

      {/* code generation failed — a real error, never substituted */}
      {genStatus === 'failed' && (
        <div
          className="flex items-start gap-2 border-b px-5 py-2.5"
          style={{
            borderColor: 'var(--as-border)',
            background: 'color-mix(in oklch, var(--as-error) 8%, transparent)',
          }}
          role="alert"
        >
          <ShieldAlert size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--as-error)' }} />
          <div className="min-w-0 text-[12px] leading-relaxed" style={{ color: 'var(--as-text-2)' }}>
            <span className="label-xs mr-1.5" style={{ color: 'var(--as-error)' }}>
              Code generation failed
            </span>
            {genMessage || 'The configured LLM provider did not return usable code. Nothing was substituted.'}
          </div>
        </div>
      )}

      {/* the workspace */}
      <div className="min-h-0 flex-1 p-3">
        {loading ? (
          <EmptyState
            icon={<Loader2 size={19} className="animate-spin" />}
            title="Loading session files..."
            detail={`Fetching the backend record for run ${runId.slice(0, 8)}.`}
          />
        ) : files.length > 0 ? (
          <div className="h-full">
            <SandboxIDE externalFiles={files} />
          </div>
        ) : connected || sessionStatus === 'RUNNING' || sessionStatus === 'PENDING' ? (
          <EmptyState
            icon={<Loader2 size={19} className="animate-spin" />}
            title="Waiting for code generation..."
            detail="The session is running. Generated files appear here as soon as the backend produces them."
          />
        ) : (
          <EmptyState
            icon={<Code2 size={19} />}
            title="No generated files in this session"
            detail={
              genStatus === 'failed'
                ? 'Code generation failed for this session — see the error above. No placeholder code is shown.'
                : 'This session completed without producing code files.'
            }
          />
        )}
      </div>

      {/* safety footer */}
      <div
        className="flex items-center gap-2 border-t px-5 py-2 text-[11.5px]"
        style={{
          borderColor: 'var(--as-border)',
          background: 'color-mix(in oklch, var(--as-teal) 6%, transparent)',
          color: 'var(--as-teal)',
        }}
      >
        <ShieldCheck size={12} className="shrink-0" />
        <span>
          Generated output is never executed — edit a Python file and press Run to execute
          your own copy. These files belong to session <span className="mono">{runId.slice(0, 8)}</span>.
        </span>
        <span className="mono ml-auto inline-flex items-center gap-1 text-[11px] opacity-80">
          <FileCode size={11} /> GET /objective-verification/sessions/{runId.slice(0, 8)}
        </span>
      </div>
    </div>
  )
}
