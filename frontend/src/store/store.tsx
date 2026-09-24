import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { EXPERIMENTS, newExperiment } from '../data/experiments'
import { resultFor } from '../data/result'
import { MEMORY } from '../data/memory'
import { nowStamp } from '../lib/format'
import type {
  AgentNode,
  Experiment,
  LogLine,
  MemoryEntry,
  ToastMsg,
} from '../lib/types'
import { Ctx, STAGE_DURATION, type RunState, type StoreValue } from './context'

export function StoreProvider({ children }: { children: ReactNode }) {
  const [experiments, setExperiments] = useState<Experiment[]>(EXPERIMENTS)
  const [activeId, setActiveId] = useState(EXPERIMENTS[0].id)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [toasts, setToasts] = useState<ToastMsg[]>([])
  const [memory, setMemory] = useState<MemoryEntry[]>(MEMORY)
  const [runState, setRunState] = useState<RunState>({
    id: null,
    paused: false,
    startedAt: null,
    elapsedMs: 0,
    stageIndex: -1,
  })

  const timers = useRef<number[]>([])
  const pausedRef = useRef(false)
  const runningIdRef = useRef<string | null>(null)
  const experimentsRef = useRef<Experiment[]>(EXPERIMENTS)
  const toastSeq = useRef(1)
  const logSeq = useRef(10_000)

  const clearTimers = useCallback(() => {
    timers.current.forEach((t) => window.clearTimeout(t))
    timers.current = []
  }, [])

  const later = useCallback((fn: () => void, ms: number) => {
    const id = window.setTimeout(fn, ms)
    timers.current.push(id)
    return id
  }, [])

  useEffect(() => () => clearTimers(), [clearTimers])
  useEffect(() => {
    experimentsRef.current = experiments
  }, [experiments])

  const toast = useCallback((t: Omit<ToastMsg, 'id'>) => {
    const id = toastSeq.current++
    setToasts((prev) => [...prev, { ...t, id }])
    window.setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== id)), 5200)
  }, [])

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((x) => x.id !== id))
  }, [])

  const patchExperiment = useCallback((id: string, fn: (e: Experiment) => Experiment) => {
    setExperiments((prev) => {
      const next = prev.map((e) => (e.id === id ? fn(e) : e))
      experimentsRef.current = next
      return next
    })
  }, [])

  const pushLog = useCallback(
    (id: string, line: Omit<LogLine, 'id' | 'ts'>) => {
      const ts = nowStamp()
      patchExperiment(id, (e) => ({
        ...e,
        logs: [...e.logs, { ...line, id: logSeq.current++, ts }].slice(-220),
      }))
    },
    [patchExperiment],
  )

  const stop = useCallback(() => {
    clearTimers()
    pausedRef.current = false
    runningIdRef.current = null
    setRunState({ id: null, paused: false, startedAt: null, elapsedMs: 0, stageIndex: -1 })
  }, [clearTimers])

  const run = useCallback(
    (id?: string) => {
      const targetId = id ?? activeId
      const exp = experimentsRef.current.find((e) => e.id === targetId)
      if (!exp || runningIdRef.current === targetId) return

      clearTimers()
      pausedRef.current = false
      runningIdRef.current = targetId

      const resetNodes: AgentNode[] = exp.nodes.map((n) => ({
        ...n,
        state: 'idle',
        startedAt: undefined,
        elapsedMs: undefined,
      }))

      patchExperiment(targetId, (e) => ({
        ...e,
        status: 'running',
        nodes: resetNodes,
        logs: [],
        result: undefined,
        runtime: '—',
        model: '—',
        verificationStatus: 'UNVERIFIED',
      }))
      setSelectedNodeId(null)
      setRunState({ id: targetId, paused: false, startedAt: Date.now(), elapsedMs: 0, stageIndex: 0 })

      toast({ title: `Run started · ${exp.id}`, detail: `${exp.verificationLevel} verification · ${exp.budget}`, tone: 'neutral' })

      let stage = 0
      let cancelled = false

      const waitWhenPaused = (resume: () => void) => {
        if (cancelled) return
        if (pausedRef.current) {
          later(waitWhenPaused.bind(null, resume), 200)
        } else {
          resume()
        }
      }

      const startStage = () => {
        if (cancelled) return
        waitWhenPaused(() => {
          const stageNow = stage
          const nodes = experimentsRef.current.find((e) => e.id === targetId)?.nodes ?? exp.nodes
          const node = nodes[stageNow]
          if (!node) return finish()

          patchExperiment(targetId, (e) => ({
            ...e,
            nodes: e.nodes.map((n, i) =>
              i === stageNow
                ? { ...n, state: 'active', startedAt: nowStamp().slice(0, 8) }
                : i === stageNow + 1
                  ? { ...n, state: 'queued' }
                  : n,
            ),
          }))
          setRunState((s) => ({ ...s, stageIndex: stageNow }))

          pushLog(targetId, { level: 'INFO', agent: node.agent, text: `${node.action}` })
          later(
            () => pushLog(targetId, { level: 'DECISION', agent: node.agent, text: node.decision }),
            Math.min(700, STAGE_DURATION[node.stage] * 0.35),
          )
          if (node.verification.status !== 'UNVERIFIED') {
            later(
              () =>
                pushLog(targetId, {
                  level: node.verification.status === 'VERIFIED' ? 'VERIFY' : 'WARN',
                  agent: 'Verifier',
                  text: `${node.verification.status} · ${node.verification.note}`,
                }),
              Math.min(1250, STAGE_DURATION[node.stage] * 0.65),
            )
          }

          later(() => {
            if (cancelled) return
            const elapsed = node.tools.reduce((a, t) => a + t.ms, 0)
            patchExperiment(targetId, (e) => ({
              ...e,
              nodes: e.nodes.map((n, i) =>
                i === stageNow ? { ...n, state: 'done', elapsedMs: elapsed } : n,
              ),
            }))
            stage += 1
            startStage()
          }, STAGE_DURATION[node.stage])
        })
      }

      const startedAtMs = Date.now()

      const finish = () => {
        if (cancelled) return
        const elapsed = Date.now() - startedAtMs
        const secs = Math.max(1, Math.round(elapsed / 1000))
        const runtime = secs < 60 ? `${secs}s` : `${Math.floor(secs / 60)}m ${String(secs % 60).padStart(2, '0')}s`

        patchExperiment(targetId, (e) => ({
          ...e,
          status: 'completed',
          runtime,
          model: 'HistGradientBoosting',
          verificationStatus: 'VERIFIED',
          result: resultFor(e),
        }))
        pushLog(targetId, {
          level: 'VERIFY',
          agent: 'Orchestrator',
          text: `pipeline frozen · replay matched · experiment completed in ${runtime}`,
        })
        setRunState({ id: null, paused: false, startedAt: null, elapsedMs: 0, stageIndex: -1 })
        runningIdRef.current = null

        const fresh = experimentsRef.current.find((e) => e.id === targetId)
        if (fresh) {
          setMemory((prev) => [
            {
              id: `mem-${Math.floor(80 + Math.random() * 19)}`,
              experiment: fresh.name,
              problemType: fresh.metric === 'recall' ? 'Binary classification · imbalanced' : 'Supervised learning',
              datasetCharacteristics: `${fresh.dataset} · target=${fresh.target} · verified provenance`,
              successfulApproach: `Pipeline ${resultFor(fresh).bestPipeline} frozen under ${fresh.verificationLevel} verification.`,
              failedApproaches: ['Pilot candidates below metric floor were discarded before full fit.'],
              confidence: 0.82,
              reusedCount: 0,
              lastUsed: new Date().toISOString().slice(0, 10),
              whyUseful: 'Freshly completed run — evidence bundle attached; promote after a second successful reuse.',
              tags: ['fresh', fresh.verificationLevel],
            },
            ...prev,
          ])
        }

        toast({ title: 'Experiment verified', detail: `${targetId} completed · evidence bundle attached`, tone: 'success' })
      }

      later(startStage, 450)
    },
    [activeId, patchExperiment, pushLog, toast, clearTimers, later],
  )

  const pause = useCallback(() => {
    pausedRef.current = true
    setRunState((s) => ({ ...s, paused: true }))
    if (runState.id) pushLog(runState.id, { level: 'WARN', agent: 'Orchestrator', text: 'run paused by operator — workers parked' })
  }, [runState.id, pushLog])

  const resume = useCallback(() => {
    pausedRef.current = false
    setRunState((s) => ({ ...s, paused: false }))
    if (runState.id) pushLog(runState.id, { level: 'INFO', agent: 'Orchestrator', text: 'run resumed — workers reacquired' })
  }, [runState.id, pushLog])

  // live runtime ticker while running
  useEffect(() => {
    if (!runState.id || runState.paused || !runState.startedAt) return
    const iv = window.setInterval(() => {
      setRunState((s) =>
        s.startedAt ? { ...s, elapsedMs: Date.now() - s.startedAt } : s,
      )
    }, 200)
    return () => window.clearInterval(iv)
  }, [runState.id, runState.paused, runState.startedAt])

  const openExperiment = useCallback((id: string) => {
    setActiveId(id)
    setSelectedNodeId(null)
  }, [])

  const createAndRun = useCallback<StoreValue['createAndRun']>(
    (opts) => {
      const exp = newExperiment(opts)
      setExperiments((prev) => {
        const next = [exp, ...prev]
        experimentsRef.current = next
        return next
      })
      setActiveId(exp.id)
      setSelectedNodeId(null)
      toast({ title: 'Experiment queued', detail: `${exp.id} · compiling task graph`, tone: 'neutral' })
      window.setTimeout(() => run(exp.id), 350)
      return exp.id
    },
    [run, toast],
  )

  const activeExperiment =
    experiments.find((e) => e.id === activeId) ?? experiments[0]

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
      experiments,
      activeExperiment,
      selectedNodeId,
      setSelectedNodeId,
      openExperiment,
      createAndRun,
      run,
      pause,
      resume,
      stop,
      runState,
      toasts,
      toast,
      dismissToast,
      memory,
      elapsedLabel,
    }),
    [
      experiments,
      activeExperiment,
      selectedNodeId,
      openExperiment,
      createAndRun,
      run,
      pause,
      resume,
      stop,
      runState,
      toasts,
      toast,
      dismissToast,
      memory,
      elapsedLabel,
    ],
  )

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
