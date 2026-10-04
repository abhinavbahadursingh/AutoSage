import type { StoreValue } from '../store/context'
import type { ApiUser } from '../lib/api'
import { EXPERIMENT_ID, MEMORY, buildExperiment } from './fixture'
import { elapsedLabelAt, elapsedMsAt, liveStageAt } from './timeline'

const USER = {
  id: 'u-dev',
  email: 'dev@autosage.local',
  name: 'dev',
  workspaces: [],
} as unknown as ApiUser

export function makeStore(t: number): StoreValue {
  const exp = buildExperiment(t)
  const active = exp && (exp.status === 'QUEUED' || exp.status === 'RUNNING')

  return {
    user: USER,
    authReady: true,
    authError: null,

    experiments: exp ? [exp] : [],
    experimentsLoading: false,
    experimentsError: null,
    refreshExperiments: async () => {},

    activeExperiment: exp,
    selectedNodeId: null,
    setSelectedNodeId: () => {},
    openExperiment: () => {},

    createAndRun: async () => EXPERIMENT_ID,
    run: async () => {},
    stop: async () => {},
    busy: false,

    runState: active
      ? { id: exp.id, paused: false, startedAt: 0, elapsedMs: elapsedMsAt(t), stageIndex: 0 }
      : { id: null, paused: false, startedAt: null, elapsedMs: 0, stageIndex: -1 },

    toasts: [],
    toast: () => {},
    dismissToast: () => {},

    memory: MEMORY,
    memoryLoading: false,
    memoryError: null,
    searchMemory: async () => {},

    elapsedLabel: elapsedLabelAt(t),
    liveStage: liveStageAt(t),
  }
}
