import { deriveNodes } from '../data/experiments'
import type { Experiment, AgentNode, MetricPoint, StageId, MemoryEntry, LogLine } from '../lib/types'
import type { ExperimentRead } from '../lib/api'
import {
  ELAPSED_SPEED,
  METRICS_FROM,
  METRICS_TO,
  PROMPT,
  STAGE_START,
  doneStagesAt,
  liveStageAt,
  runtimeLabel,
  statusAt,
} from './timeline'

export const EXPERIMENT_ID = 'e7c1a9d4-3f58-4b21-9a6c-2d84f0b71e35'
export const EXPERIMENT_NAME = 'Predict customer churn using the uploaded dataset'

const TARGET = { recall: 0.912, precision: 0.847, roc_auc: 0.963 }

const DECISIONS: Record<StageId, string> = {
  request: 'Compiled a 9-stage task graph; recall is the optimization target.',
  discovery: 'Resolved telco_churn_2024.csv (7,043 rows × 21 columns) in the dataset registry.',
  profiling: 'Target churn is 26.5% positive; 3 numeric columns carry missing values.',
  preprocessing: 'Median imputation + one-hot encoding; customerID dropped as an identifier.',
  selection: 'Shortlist LightGBM, XGBoost and logistic regression, ranked by pilot CV recall.',
  training: 'Fitting 3 candidates in the sandbox — no network, non-root, 2 CPU / 2 GB.',
  evaluation: 'LightGBM leads on holdout recall; ROC-AUC within 0.4% of XGBoost.',
  verification: 'Metric sanity, leakage and baseline dominance gates all passed.',
  pipeline: 'Pipeline frozen with seed, splits and environment lock — replayable end to end.',
}

const INPUTS: Record<StageId, string> = {
  request: "prompt='Predict customer churn using the uploaded dataset…'",
  discovery: 'registry.list(query="telco*") → 1 candidate table',
  profiling: 'dataset=telco_churn_2024.csv · target=churn',
  preprocessing: 'profile.missing=[tenure, MonthlyCharges, TotalCharges]',
  selection: 'metric=recall · budget=12 fit-min · imbalance=weighted',
  training: 'shortlist=[lgbm, xgboost, logreg] · cv=5 · seed=17',
  evaluation: 'split=holdout · n=1,409 · predictions saved',
  verification: "ml_result={'metric': 'recall', 'value': 0.912} · attempt=1",
  pipeline: 'verifier.passed=true → freeze + export bundle',
}

const EVIDENCE: Partial<Record<StageId, string[]>> = {
  training: ['cv_folds=5 · seed=17 · stratified', 'fit_time=4.1s · 3 candidates'],
  evaluation: ['holdout_recall=0.912 · n=1,409', 'baseline_majority=0.735'],
  verification: [
    'leakage_gate=pass · ast_gate=pass',
    'holdout_recall=0.912 · n=1,409',
    'baseline_majority=0.735',
    'metric_sanity=pass · range [0,1]',
  ],
  pipeline: 'bundle=autosage_pipeline.joblib · sha256=9f2c… · seed=17',
}

const CONFIDENCE: Partial<Record<StageId, number>> = {
  request: 0.93,
  discovery: 0.99,
  profiling: 0.97,
  preprocessing: 0.91,
  selection: 0.88,
  training: 0.86,
  evaluation: 0.92,
  verification: 0.94,
  pipeline: 0.98,
}

const TOOLS: Partial<Record<StageId, { name: string; args: string; ms: number }[]>> = {
  evaluation: [
    { name: 'recompute_metric', args: 'split=holdout · metric=recall', ms: 146 },
    { name: 'compare_to_baseline', args: 'baseline=majority', ms: 39 },
  ],
  verification: [
    { name: 'search_evidence', args: 'query=recall · limit=5', ms: 84 },
    { name: 'check_leakage', args: 'graph=preprocessing', ms: 212 },
    { name: 'recompute_metric', args: 'split=holdout · metric=recall', ms: 146 },
  ],
}

const VERIF_NOTES: Partial<Record<StageId, string>> = {
  verification:
    'Recomputed from the saved holdout predictions; matches the reported value to three decimals.',
  evaluation: 'Metrics read back from the sandbox result bundle.',
  pipeline: 'Frozen artifact fingerprinted and indexed for reuse.',
}

function easeOut(p: number) {
  return 1 - Math.pow(1 - p, 3)
}

function metricsAt(t: number): MetricPoint[] {
  if (t < METRICS_FROM) return []
  const p = easeOut(Math.min(1, (t - METRICS_FROM) / (METRICS_TO - METRICS_FROM)))
  return [
    { name: 'recall', value: TARGET.recall * p },
    { name: 'precision', value: TARGET.precision * p },
    { name: 'roc_auc', value: TARGET.roc_auc * p },
  ]
}

function enrich(node: AgentNode, t: number): AgentNode {
  const s = node.stage
  const live = node.state === 'active'
  const finished = node.state === 'done'
  if (!live && !finished) return node
  return {
    ...node,
    decision: DECISIONS[s],
    input: INPUTS[s],
    confidence: CONFIDENCE[s] ?? null,
    evidence: EVIDENCE[s] ?? [],
    tools: TOOLS[s] ?? [],
    elapsedMs: live
      ? Math.max(240, (t - STAGE_START[s]) * ELAPSED_SPEED * 1000)
      : (STAGE_DURATIONS[s] ?? undefined),
    verification: {
      status: node.verification.status,
      note: VERIF_NOTES[s] ?? node.verification.note,
    },
  }
}

const STAGE_DURATIONS: Partial<Record<StageId, number>> = {
  request: 5_100,
  discovery: 5_100,
  profiling: 5_100,
  preprocessing: 5_100,
  selection: 7_500,
  training: 10_200,
  evaluation: 5_700,
  verification: 18_000,
  pipeline: 3_000,
}

export function buildExperiment(t: number): Experiment | null {
  const status = statusAt(t)
  if (!status) return null

  const live = liveStageAt(t)
  const done = doneStagesAt(t)
  const base = deriveNodes(status, { stages_completed: done }, live)
  const nodes = base.map(enrich)

  const metrics = metricsAt(t)
  const isActive = status === 'QUEUED' || status === 'RUNNING'

  return {
    id: EXPERIMENT_ID,
    workspaceId: 'w-9b12ca44',
    name: EXPERIMENT_NAME,
    description: PROMPT.slice(0, 500),
    prompt: PROMPT,
    status,
    dataset: 'telco_churn_2024.csv',
    target: 'churn',
    metric: 'recall',
    budget: '12 fit-min',
    verificationLevel: 'strict',
    model: status === 'QUEUED' ? '—' : 'lightgbm',
    runtime: isActive ? '—' : runtimeLabel(),
    verificationStatus: status === 'COMPLETED' ? 'VERIFIED' : 'UNVERIFIED',
    createdAt: '2026-09-28T13:27:40Z',
    updatedAt: '2026-09-28T13:29:30Z',
    startedAt: '2026-09-28T13:27:44Z',
    completedAt: status === 'COMPLETED' ? '2026-09-28T13:28:49Z' : null,
    errorDetail: null,
    retryCount: 0,
    maxRetries: 3,
    owner: 'dev',
    config: {
      prompt: PROMPT,
      dataset_name: 'telco_churn_2024.csv',
      target_column: 'churn',
      evaluation_metric: 'recall',
      metric: 'recall',
      task_type: 'classification',
      source: 'frontend',
    },
    resultSummary:
      metrics.length > 0
        ? {
            stages_completed: done,
            model_family: 'lightgbm',
            ml_result: {
              recall: metrics[0].value,
              precision: metrics[1].value,
              roc_auc: metrics[2].value,
            },
          }
        : { stages_completed: done, model_family: status === 'QUEUED' ? undefined : 'lightgbm' },
    metrics,
    nodes,
    logs: [] as LogLine[],
    raw: {} as ExperimentRead,
  }
}

export const MEMORY: MemoryEntry[] = [
  {
    id: 'mem-4c81',
    experiment: 'churn · recall-first LightGBM',
    problemType: 'binary_classification',
    datasetCharacteristics: 'metric=recall · 7,043 rows · 26.5% positive',
    successfulApproach: 'LightGBM + median imputation + one-hot, stratified 5-fold',
    failedApproaches: ['unweighted logistic regression — recall 0.61'],
    confidence: 0.87,
    reusedCount: 3,
    lastUsed: '2026-09-14',
    whyUseful: 'Same target balance and metric; verified winner from a prior run.',
    tags: ['binary_classification', 'churn', 'recall'],
  },
]
