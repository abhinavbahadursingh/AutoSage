import { createContext, useContext } from 'react'
import type { ApiUser } from '../lib/api'
import type {
  Experiment,
  MemoryEntry,
  StageId,
  ToastMsg,
  VerificationLevel,
} from '../lib/types'

export interface RunState {
  id: string | null
  paused: boolean
  startedAt: number | null
  elapsedMs: number
  stageIndex: number
}

export interface CreateExperimentOpts {
  prompt: string
  dataset: string
  target: string
  metric: string
  budget: string
  verificationLevel: VerificationLevel
}

export interface StoreValue {
  /** Auth */
  user: ApiUser | null
  authReady: boolean
  authError: string | null
  setAuthError: (msg: string | null) => void
  /** Push a freshly-logged-in user into the store (login pages call this). */
  setUser: (u: ApiUser | null) => void
  logout: () => Promise<void>

  /** Experiments (backend-backed) */
  experiments: Experiment[]
  experimentsLoading: boolean
  experimentsError: string | null
  refreshExperiments: () => Promise<void>

  activeExperiment: Experiment | null
  selectedNodeId: string | null
  setSelectedNodeId: (id: string | null) => void
  openExperiment: (id: string) => void

  /** Create via POST /experiments then optionally start. Returns experiment id. */
  createAndRun: (opts: CreateExperimentOpts, options?: { start?: boolean }) => Promise<string>
  /** Start / re-run via POST /experiments/{id}/start */
  run: (id?: string) => Promise<void>
  /** Cancel via POST /experiments/{id}/cancel (backend has no pause). */
  stop: (id?: string) => Promise<void>
  /** True while a start/create request is in flight */
  busy: boolean

  runState: RunState
  toasts: ToastMsg[]
  toast: (t: Omit<ToastMsg, 'id'>) => void
  dismissToast: (id: number) => void

  memory: MemoryEntry[]
  memoryLoading: boolean
  memoryError: string | null
  searchMemory: (query: string) => Promise<void>

  elapsedLabel: string
  /** Live stage from WS/poll for the active experiment */
  liveStage: StageId | null
}

export const Ctx = createContext<StoreValue | null>(null)

export function useStore(): StoreValue {
  const v = useContext(Ctx)
  if (!v) throw new Error('useStore must be used within StoreProvider')
  return v
}

/** Kept for legacy UI progress math; not used for backend simulation. */
export const STAGE_DURATION: Record<StageId, number> = {
  request: 900,
  discovery: 1500,
  profiling: 1700,
  preprocessing: 1800,
  selection: 2400,
  training: 3200,
  evaluation: 1900,
  verification: 2400,
  pipeline: 1600,
}
