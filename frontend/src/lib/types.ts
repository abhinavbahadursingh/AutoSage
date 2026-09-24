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

export type ExperimentStatus = 'draft' | 'running' | 'paused' | 'completed' | 'failed'

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
  confidence: number
  evidence: string[]
  verification: { status: VerificationStatus; note: string }
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

export interface FoldResult {
  fold: number
  trainRows: number
  valRows: number
  metric: number
  auc: number
  fitSec: number
}

export interface PipelineStep {
  index: number
  op: string
  detail: string
}

export interface ExperimentResult {
  bestPipeline: string
  pipelineSteps: PipelineStep[]
  metrics: { name: string; value: number; baseline: number; unit?: string }[]
  folds: FoldResult[]
  featureImportance: { feature: string; importance: number; direction: 'positive' | 'negative' }[]
  datasetInsights: { label: string; value: string; note?: string }[]
  reproducibility: { label: string; value: string }[]
  leakageChecks: { check: string; status: VerificationStatus; note: string }[]
}

export interface Experiment {
  id: string
  name: string
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
  owner: string
  nodes: AgentNode[]
  logs: LogLine[]
  result?: ExperimentResult
}

export interface EvidenceClaim {
  id: string
  claim: string
  source: string
  agent: string
  experiment: string
  status: VerificationStatus
  confidence: number
  supporting: string[]
  conflicting?: string[]
  timestamp: string
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
