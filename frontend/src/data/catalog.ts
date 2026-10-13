import type { ModelRecord } from '../lib/types'

export const MODELS: ModelRecord[] = [
  { name: 'autosage_telco_churn_v3', family: 'HistGradientBoosting', task: 'binary classification', score: 0.864, metric: 'recall', trainedOn: 'exp-0142', status: 'champion' },
  { name: 'lending_default_iso_v2', family: 'XGBoost + isotonic', task: 'binary classification', score: 0.912, metric: 'roc_auc', trainedOn: 'exp-0141', status: 'production' },
  { name: 'ticket_router_v1', family: 'TF-IDF + OneVsRest', task: 'multilabel', score: 0.812, metric: 'f1_micro', trainedOn: 'exp-0140', status: 'production' },
  { name: 'eta_eu_lgbm_v4', family: 'LightGBM', task: 'regression', score: 6.41, metric: 'mae', trainedOn: 'exp-0139', status: 'candidate' },
  { name: 'readmit_catboost_v2', family: 'CatBoost', task: 'binary classification', score: 0.879, metric: 'recall', trainedOn: 'exp-0137', status: 'production' },
  { name: 'telco_logreg_baseline', family: 'LogisticRegression', task: 'binary classification', score: 0.712, metric: 'recall', trainedOn: 'exp-0136', status: 'archived' },
  { name: 'fraud_xgb_leakflag', family: 'XGBoost', task: 'binary classification', score: 0.0, metric: 'precision_at_k', trainedOn: 'exp-0138', status: 'archived' },
]

export const SYSTEM_SERVICES = [
  { name: 'orchestrator', status: 'online', detail: '8 workers · queue depth 0', uptime: '14d 02h' },
  { name: 'verification-engine', status: 'online', detail: 'strict recompute · avg 2.9s', uptime: '14d 02h' },
  { name: 'evidence-store', status: 'online', detail: '1,284 claims · 4 quarantined', uptime: '31d 09h' },
  { name: 'memory-index', status: 'online', detail: '77 entries · rebuilt 4h ago', uptime: '31d 09h' },
  { name: 'dataset-registry', status: 'online', detail: '7 datasets · all digests valid', uptime: '31d 09h' },
  { name: 'artifact-store', status: 'degraded', detail: 'write p99 410ms (target 250ms)', uptime: '2d 11h' },
  { name: 'scheduler', status: 'online', detail: '4 concurrent runs · 2 slots free', uptime: '14d 02h' },
  { name: 'audit-log', status: 'online', detail: 'append-only · mirrored', uptime: '31d 09h' },
]
