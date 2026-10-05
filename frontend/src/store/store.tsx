import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  api,
  ApiError,
  ensureToken,
  experimentWsUrl,
  getToken,
  setToken,
  setCachedUser,
  type ApiUser,
  type ExperimentRead,
} from '../lib/api'
import { nowStamp } from '../lib/format'
import {
  deriveNodes,
  mapExperiment,
  stageFromBackend,
  STAGE_META,
  userName,
} from '../data/experiments'
import type { Experiment, LogLine, MemoryEntry, StageId, ToastMsg } from '../lib/types'
import { Ctx, type RunState, type StoreValue } from './context'

const ACTIVE_STATUSES = new Set(['QUEUED', 'RUNNING', 'RETRYING'])
const POLL_MS = 2500
const LOG_KEY_PREFIX = 'as_logs_'

function loadLogs(id: string): LogLine[] {
  try {
    const raw = window.localStorage.getItem(LOG_KEY_PREFIX + id)
    if (!raw) return []
    const parsed = JSON.parse(raw) as LogLine[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveLogs(id: string, logs: LogLine[]): void {
  try {
    window.localStorage.setItem(LOG_KEY_PREFIX + id, JSON.stringify(logs.slice(-200)))
  } catch {
    /* ignore */
  }
}

function memoryFromSearch(query: string, results: { id: string; memory_type: string; task_type: string; solution_strategy: string; achieved_metric_value: number | null; metric_name: string | null; similarity_score: number; created_at: string | null }[]): MemoryEntry[] {
  return results.map((r) => ({
    id: r.id,
    experiment: r.task_type || query || 'memory',
    problemType: r.memory_type,
    datasetCharacteristics: r.metric_name ? `metric=${r.metric_name}` : '—',
    successfulApproach: r.solution_strategy || '—',
    failedApproaches: [],
    confidence: Math.max(0, Math.min(1, r.similarity_score ?? 0)),
    reusedCount: 0,
    lastUsed: r.created_at ? r.created_at.slice(0, 10) : '—',
    whyUseful: r.solution_strategy || 'Indexed memory entry from backend search.',
    tags: [r.memory_type],
  }))
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<ApiUser | null>(null)
  const [authReady, setAuthReady] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [experimentsLoading, setExperimentsLoading] = useState(true)
  const [experimentsError, setExperimentsError] = useState<string | null>(null)

  const [activeId, setActiveId] = useState<string | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [toasts, setToasts] = useState<ToastMsg[]>([])
  const [memory, setMemory] = useState<MemoryEntry[]>([])
  const [memoryLoading, setMemoryLoading] = useState(false)
  const [memoryError, setMemoryError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [liveStage, setLiveStage] = useState<StageId | null>(null)
  const [runState, setRunState] = useState<RunState>({
    id: null,
    paused: false,
    startedAt: null,
    elapsedMs: 0,
    stageIndex: -1,
  })

  const experimentsRef = useRef<Experiment[]>([])
  const activeIdRef = useRef<string | null>(null)
  const logsRef = useRef<Record<string, LogLine[]>>({})
  const liveStageRef = useRef<StageId | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  // Generation counter: only the latest connectWs may open a socket.
  const connectSeq = useRef(0)
  // Event dedup: one delivery per (experiment, event_type, timestamp).
  const seenEvents = useRef(new Set<string>())
  const pollRef = useRef<number | null>(null)
  const toastSeq = useRef(1)
  const logSeq = useRef(10_000)
  const ownerRef = useRef('you')

  useEffect(() => {
    experimentsRef.current = experiments
  }, [experiments])
  useEffect(() => {
    activeIdRef.current = activeId
  }, [activeId])
  useEffect(() => {
    liveStageRef.current = liveStage
  }, [liveStage])

  const toast = useCallback((t: Omit<ToastMsg, 'id'>) => {
    const id = toastSeq.current++
    setToasts((prev) => [...prev, { ...t, id }])
    window.setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== id)), 5200)
  }, [])

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((x) => x.id !== id))
  }, [])

  const pushLog = useCallback((id: string, line: Omit<LogLine, 'id' | 'ts'>) => {
    const ts = nowStamp()
    const existing = logsRef.current[id] ?? loadLogs(id)
    const next = [...existing, { ...line, id: logSeq.current++, ts }].slice(-200)
    logsRef.current[id] = next
    saveLogs(id, next)
    console.info(`[autosage:${id.slice(0, 8)}] [${line.level}] ${line.agent}: ${line.text}`)
    setExperiments((prev) =>
      prev.map((e) => (e.id === id ? { ...e, logs: next } : e)),
    )
  }, [])

  const applyRaw = useCallback((raw: ExperimentRead) => {
    const stage = liveStageRef.current
    const logs = logsRef.current[raw.id] ?? loadLogs(raw.id)
    logsRef.current[raw.id] = logs
    const mapped = mapExperiment(raw, ownerRef.current, stage, logs)
    setExperiments((prev) => {
      const idx = prev.findIndex((e) => e.id === raw.id)
      if (idx === -1) return [mapped, ...prev]
      const next = [...prev]
      next[idx] = mapped
      return next
    })
    return mapped
  }, [])

  const refreshExperiments = useCallback(async () => {
    setExperimentsLoading(true)
    setExperimentsError(null)
    try {
      const page = await api.listExperiments({ page: 1, page_size: 100 })
      const mapped = page.items.map((raw) => {
        const logs = logsRef.current[raw.id] ?? loadLogs(raw.id)
        logsRef.current[raw.id] = logs
        return mapExperiment(raw, ownerRef.current, liveStageRef.current, logs)
      })
      setExperiments(mapped)
      setActiveId((prev) => {
        if (prev && mapped.some((e) => e.id === prev)) return prev
        return mapped[0]?.id ?? null
      })
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to load experiments'
      setExperimentsError(msg)
      toast({ title: 'Could not load experiments', detail: msg, tone: 'error' })
    } finally {
      setExperimentsLoading(false)
    }
  }, [toast])

  const searchMemory = useCallback(
    async (query: string) => {
      setMemoryLoading(true)
      setMemoryError(null)
      try {
        const res = await api.searchMemory(query || 'experiment')
        setMemory(memoryFromSearch(res.query, res.results))
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : 'Memory search failed'
        setMemoryError(msg)
        setMemory([])
      } finally {
        setMemoryLoading(false)
      }
    },
    [],
  )

  // Bootstrap auth + initial data.
  // Production with no stored token: bootstrapAuth throws "sign in required"
  // (it never calls the dev-token endpoint). That is a normal logged-out
  // state — set the auth error so ProtectedRoute redirects to /login, but
  // skip the error toast (the Login page explains the next step).
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const hadToken = getToken() !== null
      try {
        const u = await api.bootstrapAuth()
        if (cancelled) return
        ownerRef.current = userName(u)
        setUser(u)
        setAuthError(null)
        await refreshExperiments()
        await searchMemory('')
      } catch (err) {
        if (cancelled) return
        const msg = err instanceof ApiError ? err.message : 'Authentication failed'
        setAuthError(msg)
        const quietLoggedOut =
          err instanceof ApiError && err.status === 401 && !hadToken
        if (!quietLoggedOut) {
          toast({ title: 'Backend auth failed', detail: msg, tone: 'error' })
        }
      } finally {
        if (!cancelled) setAuthReady(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [refreshExperiments, searchMemory, toast])

  const closeWs = useCallback(() => {
    ++connectSeq.current // invalidate any in-flight connect
    if (wsRef.current) {
      try {
        wsRef.current.close()
      } catch {
        /* ignore */
      }
      wsRef.current = null
    }
  }, [])

  const connectWs = useCallback(
    (experimentId: string, retried = false) => {
      closeWs() // bumps connectSeq + tears down socket
      const seq = connectSeq.current
      void ensureToken(retried).then((t) => {
        if (activeIdRef.current !== experimentId || seq !== connectSeq.current) return
        try {
          const ws = new WebSocket(experimentWsUrl(experimentId, t))
          wsRef.current = ws
          let opened = false
          ws.onopen = () => {
            opened = true
          }
          ws.onmessage = (ev) => {
            try {
              const msg = JSON.parse(ev.data as string) as {
                type?: string
                event?: {
                  event_type?: string
                  timestamp?: string
                  payload?: Record<string, unknown>
                }
                message?: string
              }
              if (msg.type === 'ack') {
                pushLog(experimentId, {
                  level: 'INFO',
                  agent: 'System',
                  text: msg.message ?? 'Connected to experiment stream',
                })
                return
              }
              if (msg.type !== 'event' || !msg.event) return
              const et = msg.event.event_type ?? ''
              const p = msg.event.payload ?? {}
              // One delivery per (experiment, event_type, timestamp). Backend
              // broadcasts each event once per WS connection, but duplicate
              // connections/reconnects would otherwise re-toast every event.
              const eventKey = `${experimentId}:${et}:${msg.event.timestamp ?? JSON.stringify(p)}`
              if (seenEvents.current.has(eventKey)) return
              seenEvents.current.add(eventKey)
              if (seenEvents.current.size > 500) seenEvents.current.clear()
              if (et === 'agent.started' || et === 'agent.completed' || et === 'agent.failed') {
                const stage = stageFromBackend(String(p.stage ?? p.agent_name ?? ''))
                if (stage) {
                  setLiveStage(stage)
                  const meta = STAGE_META.find((m) => m.id === stage)
                  const level =
                    et === 'agent.failed' ? 'WARN' : et === 'agent.completed' ? 'DECISION' : 'INFO'
                  pushLog(experimentId, {
                    level,
                    agent: String(p.agent_name ?? meta?.agent ?? 'Agent'),
                    text:
                      et === 'agent.started'
                        ? `stage started · ${String(p.stage ?? stage)}`
                        : et === 'agent.completed'
                          ? `stage completed · ${String(p.stage ?? stage)}`
                          : `stage failed · ${String(p.error ?? '')}`,
                  })
                }
              } else if (et === 'agent.warning') {
                pushLog(experimentId, {
                  level: 'WARN',
                  agent: String(p.agent_name ?? 'Agent'),
                  text: `⚠ ${String(p.warning ?? 'LLM fallback')}${p.error ? ` · ${String(p.error)}` : ''}`,
                })
                toast({
                  title: 'LLM model unavailable',
                  detail: String(p.error ?? p.warning ?? 'Heuristic fallback in use'),
                  tone: 'warn',
                })
              } else if (et === 'experiment.started') {
                pushLog(experimentId, {
                  level: 'INFO',
                  agent: 'Orchestrator',
                  text: `experiment started · ${String(p.experiment_name ?? '')}`,
                })
                setLiveStage('request')
              } else if (et === 'ml.started') {
                setLiveStage('training')
                pushLog(experimentId, {
                  level: 'INFO',
                  agent: 'Trainer',
                  text: `ml started · family=${String(p.model_family ?? '—')}`,
                })
              } else if (et === 'ml.completed') {
                setLiveStage('evaluation')
                pushLog(experimentId, {
                  level: p.success ? 'METRIC' : 'WARN',
                  agent: 'Evaluator',
                  text: p.success
                    ? `ml completed · metrics=${JSON.stringify(p.metrics ?? {})}`
                    : `ml failed · ${String(p.error ?? '')}`,
                })
              } else if (et === 'verification.started' || et === 'verification.completed') {
                setLiveStage('verification')
                pushLog(experimentId, {
                  level: et === 'verification.completed' && p.passed ? 'VERIFY' : 'INFO',
                  agent: 'Verifier',
                  text:
                    et === 'verification.started'
                      ? `verification attempt ${String(p.attempt ?? '?')}/${String(p.max_attempts ?? '?')}`
                      : `verification ${p.passed ? 'passed' : 'did not pass'} · gate=${String(p.gate_decision ?? '')}`,
                })
              } else if (et === 'experiment.completed') {
                setLiveStage('pipeline')
                pushLog(experimentId, {
                  level: 'VERIFY',
                  agent: 'Orchestrator',
                  text: 'experiment completed',
                })
                void api.getExperiment(experimentId).then(applyRaw).catch(() => undefined)
              } else if (et === 'experiment.failed') {
                pushLog(experimentId, {
                  level: 'WARN',
                  agent: 'Orchestrator',
                  text: `experiment failed · ${String(p.error_detail ?? '')}`,
                })
                void api.getExperiment(experimentId).then(applyRaw).catch(() => undefined)
              }
            } catch {
              /* ignore malformed frames */
            }
          }
          ws.onerror = () => {
            /* polling remains the fallback */
          }
          ws.onclose = (ev) => {
            if (wsRef.current === ws) wsRef.current = null
            // Unknown/deleted experiment (backend closes 1008 with reason):
            // retrying with a fresh token can never help, and the poller's
            // 404 handler owns state cleanup — just note it and stop.
            // Auth failures ("Authentication required") still fall through
            // to the token-refresh retry below.
            const reason = typeof ev.reason === 'string' ? ev.reason : ''
            if (ev.code === 1008 && /not found|forbidden/i.test(reason)) {
              pushLog(experimentId, {
                level: 'WARN',
                agent: 'System',
                text: 'experiment not available on event stream · using polling fallback',
              })
              return
            }
            // Handshake failed (auth/network): force a fresh token and retry once.
            if (!opened && !retried && activeIdRef.current === experimentId) {
              window.setTimeout(() => {
                if (activeIdRef.current === experimentId) connectWs(experimentId, true)
              }, 400)
              return
            }
            if (!opened) {
              pushLog(experimentId, {
                level: 'WARN',
                agent: 'System',
                text: `event stream closed before open (code=${ev.code}) · polling continues`,
              })
            }
          }
        } catch {
          /* WS optional — polling still works */
        }
      }).catch(() => {
        /* No token (logged out) or WS setup failed — polling still works */
      })
    },
    [applyRaw, closeWs, pushLog],
  )

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const startPolling = useCallback(
    (experimentId: string) => {
      stopPolling()
      pollRef.current = window.setInterval(() => {
        void api
          .getExperiment(experimentId)
          .then((raw) => {
            applyRaw(raw)
            if (!ACTIVE_STATUSES.has(raw.status)) {
              stopPolling()
              closeWs()
              setLiveStage(null)
              setRunState({ id: null, paused: false, startedAt: null, elapsedMs: 0, stageIndex: -1 })
              if (raw.status === 'COMPLETED') {
                toast({
                  title: 'Experiment completed',
                  detail: raw.name,
                  tone: 'success',
                })
              } else if (raw.status === 'FAILED') {
                toast({
                  title: 'Experiment failed',
                  detail: raw.error_detail ?? raw.name,
                  tone: 'error',
                })
              }
              void refreshExperiments()
            }
          })
          .catch((err) => {
            if (err instanceof ApiError && (err.status === 404 || err.status === 403)) {
              // Target vanished (deleted, or belongs to another user/session).
              // A 404 never resolves into a terminal status, so without this
              // the poller would hit NOT_FOUND every 2.5s forever. Drop the
              // stale ID once: stop everything, forget it, fall through to
              // the latest experiment via refresh (its keeper adopts list[0]
              // when the current ID is gone, which re-arms poll+WS there).
              if (activeIdRef.current !== experimentId) return
              stopPolling()
              closeWs()
              setLiveStage(null)
              setRunState({ id: null, paused: false, startedAt: null, elapsedMs: 0, stageIndex: -1 })
              setExperiments((prev) => prev.filter((e) => e.id !== experimentId))
              setActiveId((prev) => (prev === experimentId ? null : prev))
              setSelectedNodeId(null)
              delete logsRef.current[experimentId]
              try {
                window.localStorage.removeItem(LOG_KEY_PREFIX + experimentId)
              } catch {
                /* ignore */
              }
              toast({
                title: 'Experiment no longer available',
                detail: 'It may have been deleted or belong to another session. Showing the latest experiment instead.',
                tone: 'warn',
              })
              void refreshExperiments()
              return
            }
            /* keep polling; transient errors surface on manual refresh */
          })
      }, POLL_MS)
    },
    [applyRaw, closeWs, refreshExperiments, stopPolling, toast],
  )

  useEffect(() => () => {
    stopPolling()
    closeWs()
  }, [stopPolling, closeWs])

  // Reconnect WS / polling when active experiment is active
  useEffect(() => {
    const exp = experiments.find((e) => e.id === activeId)
    if (exp && ACTIVE_STATUSES.has(exp.status)) {
      setLiveStage((prev) => prev)
      setRunState((s) =>
        s.id === exp.id
          ? s
          : {
              id: exp.id,
              paused: false,
              startedAt: exp.startedAt ? new Date(exp.startedAt).getTime() : Date.now(),
              elapsedMs: 0,
              stageIndex: 0,
            },
      )
      connectWs(exp.id)
      startPolling(exp.id)
    } else {
      stopPolling()
      if (exp && !ACTIVE_STATUSES.has(exp.status)) {
        closeWs()
        setLiveStage(null)
        setRunState({ id: null, paused: false, startedAt: null, elapsedMs: 0, stageIndex: -1 })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId, experiments.find((e) => e.id === activeId)?.status])

  // Elapsed ticker
  useEffect(() => {
    if (!runState.id || !runState.startedAt) return
    const iv = window.setInterval(() => {
      setRunState((s) => (s.startedAt ? { ...s, elapsedMs: Date.now() - s.startedAt } : s))
    }, 200)
    return () => window.clearInterval(iv)
  }, [runState.id, runState.startedAt])

  const openExperiment = useCallback((id: string) => {
    setActiveId(id)
    setSelectedNodeId(null)
  }, [])

  const ensureWorkspace = useCallback(async (): Promise<string> => {
    const list = await api.listWorkspaces(1, 20)
    const first = list.items[0]
    if (first) return first.id
    const created = await api.createWorkspace({ name: 'Default Workspace' })
    return created.id
  }, [])

  const createAndRun = useCallback<StoreValue['createAndRun']>(
    async (opts, options) => {
      const shouldStart = options?.start ?? true
      setBusy(true)
      console.info('[autosage] Run Experiment clicked · building config…')
      try {
        const workspaceId = await ensureWorkspace()
        const title = opts.prompt.trim().split(/[.\n]/)[0]?.slice(0, 58) || 'Untitled experiment'
        const name = title.charAt(0).toUpperCase() + title.slice(1)

        // Only backend-allowed config keys (see schemas/experiment.py).
        const taskType =
          /regress|eta|forecast|price|amount|mae|rmse/i.test(opts.prompt) ? 'regression' : 'classification'
        const config: Record<string, unknown> = {
          prompt: opts.prompt,
          dataset: opts.dataset,
          dataset_name: opts.dataset,
          target_column: opts.target,
          evaluation_metric: opts.metric,
          source: 'frontend',
          task_type: taskType,
        }
        // metric key only when backend allows it
        const allowedMetrics = new Set([
          'accuracy',
          'precision',
          'recall',
          'f1',
          'roc_auc',
          'log_loss',
          'mse',
          'mae',
          'rmse',
          'r2',
        ])
        if (allowedMetrics.has(opts.metric)) {
          config.metric = opts.metric
        }
        config.split_strategy = 'random'
        config.imbalance_handling = 'none'

        const created = await api.createExperiment({
          name,
          description: opts.prompt.slice(0, 500),
          workspace_id: workspaceId,
          config,
          max_retries: 3,
        })
        console.info(`[autosage] POST /experiments → created · status=${created.status}`)

        pushLog(created.id, {
          level: 'INFO',
          agent: 'Orchestrator',
          text: `experiment created · ${created.status}`,
        })

        if (shouldStart) {
          console.info(`[autosage] POST /experiments/${created.id}/start → dispatching Celery task…`)
          const started = await api.startExperiment(created.id)
          console.info(`[autosage] start accepted · status=${started.status} → workflow: orchestrator → discovery → profiler → preprocessor → model_selector → ml_experiment → verification`)
          applyRaw(started)
        pushLog(created.id, {
          level: 'INFO',
          agent: 'System',
          text: `start accepted · status=${started.status}`,
        })
        const stagePlan: Array<[string, string]> = [
          ['Orchestrator', 'compiling prompt into task graph'],
          ['Discovery', 'scanning dataset schema · detecting target/task type'],
          ['Profiler', 'profiling distributions · missingness · drift'],
          ['Preprocessor', 'building feature pipeline · split strategy'],
          ['ModelSelector', 'shortlisting candidate models for the budget'],
          ['Experimenter', 'running fits · cross-validation pilots'],
          ['Verifier', 'recompute + verification gate before freeze'],
        ]
        for (const [agent, text] of stagePlan) {
          pushLog(created.id, { level: 'INFO', agent, text: `queued — ${text}` })
        }
          toast({
            title: 'Experiment started',
            detail: `${started.name} · ${started.status}`,
            tone: 'neutral',
          })
        } else {
          applyRaw(created)
          toast({
            title: 'Experiment created',
            detail: created.name,
            tone: 'neutral',
          })
        }

        setActiveId(created.id)
        setSelectedNodeId(null)
        await refreshExperiments()
        return created.id
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : 'Failed to create experiment'
        toast({ title: 'Create failed', detail: msg, tone: 'error' })
        throw err
      } finally {
        setBusy(false)
      }
    },
    [applyRaw, ensureWorkspace, pushLog, refreshExperiments, toast],
  )

  const run = useCallback(
    async (id?: string) => {
      const targetId = id ?? activeIdRef.current
      if (!targetId) return
      setBusy(true)
      try {
        setLiveStage(null)
        const started = await api.startExperiment(targetId)
        applyRaw(started)
        // Display must agree with what connectWs/startPolling target below —
        // otherwise the UI shows one experiment while another is polled.
        setActiveId(targetId)
        setSelectedNodeId(null)
        pushLog(targetId, {
          level: 'INFO',
          agent: 'System',
          text: `start accepted · status=${started.status}`,
        })
        toast({
          title: `Run started`,
          detail: `${started.name} · ${started.status}`,
          tone: 'neutral',
        })
        setRunState({
          id: targetId,
          paused: false,
          startedAt: started.started_at ? new Date(started.started_at).getTime() : Date.now(),
          elapsedMs: 0,
          stageIndex: 0,
        })
        connectWs(targetId)
        startPolling(targetId)
        await refreshExperiments()
      } catch (err) {
        if (err instanceof ApiError && (err.status === 404 || err.status === 403)) {
          // Start target is gone (deleted / another user): drop it the same
          // way the poller's 404 handler does, instead of leaving a stale
          // active ID behind. Its toast explains the situation.
          stopPolling()
          closeWs()
          setLiveStage(null)
          setRunState({ id: null, paused: false, startedAt: null, elapsedMs: 0, stageIndex: -1 })
          setExperiments((prev) => prev.filter((e) => e.id !== targetId))
          setActiveId((prev) => (prev === targetId ? null : prev))
          setSelectedNodeId(null)
          delete logsRef.current[targetId]
          try {
            window.localStorage.removeItem(LOG_KEY_PREFIX + targetId)
          } catch {
            /* ignore */
          }
          toast({
            title: 'Experiment no longer available',
            detail: 'It may have been deleted or belong to another session. Showing the latest experiment instead.',
            tone: 'warn',
          })
          void refreshExperiments()
          return
        }
        const msg = err instanceof ApiError ? err.message : 'Failed to start experiment'
        toast({ title: 'Start failed', detail: msg, tone: 'error' })
      } finally {
        setBusy(false)
      }
    },
    [applyRaw, closeWs, connectWs, pushLog, refreshExperiments, startPolling, stopPolling, toast],
  )

  const stop = useCallback(
    async (id?: string) => {
      const targetId = id ?? activeIdRef.current
      if (!targetId) return
      setBusy(true)
      try {
        const cancelled = await api.cancelExperiment(targetId)
        applyRaw(cancelled)
        pushLog(targetId, {
          level: 'WARN',
          agent: 'Orchestrator',
          text: 'run cancelled by operator',
        })
        toast({ title: 'Experiment cancelled', detail: cancelled.name, tone: 'warn' })
        stopPolling()
        closeWs()
        setLiveStage(null)
        setRunState({ id: null, paused: false, startedAt: null, elapsedMs: 0, stageIndex: -1 })
        await refreshExperiments()
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : 'Failed to cancel experiment'
        toast({ title: 'Cancel failed', detail: msg, tone: 'error' })
      } finally {
        setBusy(false)
      }
    },
    [applyRaw, closeWs, pushLog, refreshExperiments, stopPolling, toast],
  )

  const logout = useCallback(async () => {
    setToken(null)
    setCachedUser(null)
    setUser(null)
    setAuthError(null)
    setExperiments([])
    setActiveId(null)
    setSelectedNodeId(null)
    setMemory([])
    stopPolling()
    closeWs()
    setLiveStage(null)
    setRunState({ id: null, paused: false, startedAt: null, elapsedMs: 0, stageIndex: -1 })
    toast({ title: 'Signed out', detail: 'You have been logged out', tone: 'neutral' })
  }, [closeWs, stopPolling, toast])

  const activeExperiment = useMemo(() => {
    if (!activeId) return experiments[0] ?? null
    return experiments.find((e) => e.id === activeId) ?? experiments[0] ?? null
  }, [activeId, experiments])

  // Keep liveStage reflected into nodes for active experiment
  useEffect(() => {
    if (!activeId) return
    setExperiments((prev) =>
      prev.map((e) => {
        if (e.id !== activeId) return e
        const nodes = deriveNodes(e.status, e.resultSummary, liveStage)
        return { ...e, nodes }
      }),
    )
  }, [liveStage, activeId])

  const elapsedLabel = useMemo(() => {
    const ms = runState.elapsedMs
    const totalSec = Math.floor(ms / 1000)
    const mm = String(Math.floor(totalSec / 60)).padStart(2, '0')
    const ss = String(totalSec % 60).padStart(2, '0')
    const t = Math.floor((ms % 1000) / 100)
    return `${mm}:${ss}.${t}`
  }, [runState.elapsedMs])

  const value = useMemo<StoreValue>(
    () => ({
      user,
      authReady,
      authError,
      setAuthError,
      setUser,
      logout,
      experiments,
      experimentsLoading,
      experimentsError,
      refreshExperiments,
      activeExperiment,
      selectedNodeId,
      setSelectedNodeId,
      openExperiment,
      createAndRun,
      run,
      stop,
      busy,
      runState,
      toasts,
      toast,
      dismissToast,
      memory,
      memoryLoading,
      memoryError,
      searchMemory,
      elapsedLabel,
      liveStage,
    }),
    [
      user,
      authReady,
      authError,
      setAuthError,
      setUser,
      logout,
      experiments,
      experimentsLoading,
      experimentsError,
      refreshExperiments,
      activeExperiment,
      selectedNodeId,
      openExperiment,
      createAndRun,
      run,
      stop,
      busy,
      runState,
      toasts,
      toast,
      dismissToast,
      memory,
      memoryLoading,
      memoryError,
      searchMemory,
      elapsedLabel,
      liveStage,
    ],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export { useStore } from './context'
