import type { ApiExperimentStatus, ExperimentRead } from './api'

export type StageId =
  | 'request'
  | 'discovery'
  | 'profiling'
  | 'preprocessing'
  | 'selection'
  | 'training'
  | 'evaluation'
  | 'verification'
  | 'pipeline'

export type NodeState = 'idle' | 'queued' | 'active' | 'done' | 'failed'

/** Backend experiment lifecycle (ExperimentStatus str enum). */
export type ExperimentStatus = ApiExperimentStatus

export type VerificationStatus = 'VERIFIED' | 'UNVERIFIED' | 'CONFLICTING' | 'QUARANTINED'

export type VerificationLevel = 'strict' | 'standard' | 'fast'

export interface ToolCall {
  name: string
  args: string
  ms: number
}

export interface AgentNode {
  id: string
  stage: StageId
  agent: string
  role: string
  state: NodeState
  action: string
  idleAction: string
  input: string
  decision: string
  confidence: number | null
  evidence: string[]
  verification: { status: VerificationStatus; note: string }
  verification_abstained?: boolean
  tools: ToolCall[]
  startedAt?: string
  elapsedMs?: number
}

export interface LogLine {
  id: number
  ts: string
  level: 'INFO' | 'DECISION' | 'VERIFY' | 'WARN' | 'METRIC'
  agent: string
  text: string
}

export interface MetricPoint {
  name: string
  value: number
}

export interface Experiment {
  /** Backend UUID */
  id: string
  workspaceId: string
  name: string
  description: string | null
  prompt: string
  status: ExperimentStatus
  dataset: string
  target: string
  metric: string
  budget: string
  verificationLevel: VerificationLevel
  model: string
  runtime: string
  verificationStatus: VerificationStatus
  createdAt: string
  updatedAt: string
  startedAt: string | null
  completedAt: string | null
  errorDetail: string | null
  retryCount: number
  maxRetries: number
  owner: string
  config: Record<string, unknown>
  resultSummary: Record<string, unknown>
  metrics: MetricPoint[]
  nodes: AgentNode[]
  logs: LogLine[]
  /** Raw backend payload for adapters/debugging */
  raw: ExperimentRead
}

export interface MemoryEntry {
  id: string
  experiment: string
  problemType: string
  datasetCharacteristics: string
  successfulApproach: string
  failedApproaches: string[]
  confidence: number
  reusedCount: number
  lastUsed: string
  whyUseful: string
  tags: string[]
}

export interface DatasetRecord {
  name: string
  rows: number
  columns: number
  size: string
  target?: string
  task: string
  missing: number
  updated: string
  tags: string[]
}

export interface ModelRecord {
  name: string
  family: string
  task: string
  score: number
  metric: string
  trainedOn: string
  status: 'production' | 'champion' | 'candidate' | 'archived'
}

export interface ToastMsg {
  id: number
  title: string
  detail?: string
  tone: 'neutral' | 'success' | 'warn' | 'error'
}
