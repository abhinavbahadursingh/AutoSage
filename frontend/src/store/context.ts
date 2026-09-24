import { createContext, useContext } from 'react'
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

export interface StoreValue {
  experiments: Experiment[]
  activeExperiment: Experiment
  selectedNodeId: string | null
  setSelectedNodeId: (id: string | null) => void
  openExperiment: (id: string) => void
  createAndRun: (opts: {
    prompt: string
    dataset: string
    target: string
    metric: string
    budget: string
    verificationLevel: VerificationLevel
  }) => string
  run: (id?: string) => void
  pause: () => void
  resume: () => void
  stop: () => void
  runState: RunState
  toasts: ToastMsg[]
  toast: (t: Omit<ToastMsg, 'id'>) => void
  dismissToast: (id: number) => void
  memory: MemoryEntry[]
  elapsedLabel: string
}

export const Ctx = createContext<StoreValue | null>(null)

export function useStore(): StoreValue {
  const v = useContext(Ctx)
  if (!v) throw new Error('useStore must be used within StoreProvider')
  return v
}

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
