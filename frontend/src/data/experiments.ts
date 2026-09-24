import type {
  AgentNode,
  Experiment,
  ExperimentResult,
  LogLine,
  StageId,
  VerificationLevel,
} from '../lib/types'

export const STAGE_META: { id: StageId; label: string; short: string }[] = [
  { id: 'request', label: 'User Request', short: 'REQ' },
  { id: 'discovery', label: 'Dataset Discovery', short: 'DISC' },
  { id: 'profiling', label: 'Profiling', short: 'PROF' },
  { id: 'preprocessing', label: 'Preprocessing', short: 'PREP' },
  { id: 'selection', label: 'Model Selection', short: 'SEL' },
  { id: 'training', label: 'Training', short: 'TRAIN' },
  { id: 'evaluation', label: 'Evaluation', short: 'EVAL' },
  { id: 'verification', label: 'Verification', short: 'VERIF' },
  { id: 'pipeline', label: 'Final Pipeline', short: 'PIPE' },
]

export const AGENT_ROSTER = [
  { id: 'orchestrator', name: 'Orchestrator', role: 'planner · router', state: 'idle' as const },
  { id: 'scout', name: 'Data Scout', role: 'retrieval · registry', state: 'idle' as const },
  { id: 'profiler', name: 'Profiler', role: 'statistics · schema', state: 'idle' as const },
  { id: 'preprocessor', name: 'Preprocessor', role: 'cleaning · encoding', state: 'idle' as const },
  { id: 'selector', name: 'Model Selector', role: 'search · ranking', state: 'idle' as const },
  { id: 'trainer', name: 'Trainer', role: 'fit · checkpoint', state: 'idle' as const },
  { id: 'evaluator', name: 'Evaluator', role: 'metrics · slices', state: 'idle' as const },
  { id: 'verifier', name: 'Verifier', role: 'claims · evidence', state: 'online' as const },
]

type NodeSpec = Omit<AgentNode, 'state' | 'elapsedMs' | 'startedAt'>

const CHURN_NODES: NodeSpec[] = [
  {
    id: 'n-request',
    stage: 'request',
    agent: 'Orchestrator',
    role: 'planner · router',
    action: 'Parsed intent, constraints and success criteria from natural-language request.',
    idleAction: 'Awaiting a task description.',
    input:
      '"Predict customer churn using the uploaded dataset. Compare several models and optimize for recall."',
    decision:
      'Binary classification · target churn · optimize recall at fixed precision ≥ 0.60 · budget 12 fit-minutes · strict verification.',
    confidence: 0.97,
    evidence: ['intent.parse#3', 'user.constraints.budget', 'policy.default_metric_map'],
    verification: { status: 'VERIFIED', note: 'Intent schema validated against task grammar v4.' },
    tools: [
      { name: 'intent.parse', args: 'prompt, locale=en', ms: 41 },
      { name: 'budget.resolve', args: 'tier=standard', ms: 6 },
    ],
  },
  {
    id: 'n-discovery',
    stage: 'discovery',
    agent: 'Data Scout',
    role: 'retrieval · registry',
    action: 'Matched request to registered datasets and verified provenance hashes.',
    idleAction: 'Scanning dataset registry for candidate tables.',
    input: 'query="customer churn", scope=workspace/uploads, k=5',
    decision:
      'Selected telco_churn_2024.csv (7,043 × 21) — exact target match, provenance signed, 0 downstream mirrors in conflict.',
    confidence: 0.94,
    evidence: ['registry.telco_churn_2024.sha256', 'upload.session#8812', 'provenance.license=CC-BY-4.0'],
    verification: { status: 'VERIFIED', note: 'Content hash matches registered manifest.' },
    tools: [
      { name: 'registry.search', args: 'q="churn", k=5', ms: 118 },
      { name: 'artifact.hash', args: 'algo=sha256', ms: 24 },
      { name: 'lineage.inspect', args: 'dataset=telco_churn_2024', ms: 37 },
    ],
  },
  {
    id: 'n-profiling',
    stage: 'profiling',
    agent: 'Profiler',
    role: 'statistics · schema',
    action: 'Computed schema, missingness, cardinality and target base rate.',
    idleAction: 'Profiling columns for type, drift and missingness.',
    input: 'telco_churn_2024.csv · 7,043 rows · 21 columns',
    decision:
      '11 categorical / 9 numeric / 1 datetime-derived. 11 missing values confined to TotalCharges (0.16%). Target base rate 26.5% → stratified splits required.',
    confidence: 0.96,
    evidence: ['profile.report#7f21', 'missingness.map', 'target.histogram.churn'],
    verification: { status: 'VERIFIED', note: 'Profiler recomputed on 10% sample — metrics within 0.4%.' },
    tools: [
      { name: 'stats.profile', args: 'full', ms: 640 },
      { name: 'schema.infer', args: 'strict=false', ms: 88 },
      { name: 'drift.baseline', args: 'reference=none', ms: 51 },
    ],
  },
  {
    id: 'n-preprocessing',
    stage: 'preprocessing',
    agent: 'Preprocessor',
    role: 'cleaning · encoding',
    action: 'Built imputation, encoding and scaling graph; checked target leakage.',
    idleAction: 'Assembling preprocessing graph.',
    input: 'profile.report#7f21 · constraints=target:churn',
    decision:
      'Median impute TotalCharges → drop customerID → one-hot top-30 categories (handle=other) → StandardScale numerics. 2 leakage probes passed (no post-outcome fields detected).',
    confidence: 0.92,
    evidence: ['leakage.probe#1', 'leakage.probe#2', 'encoding.cardinality_report'],
    verification: { status: 'VERIFIED', note: 'Feature list hashed and frozen before fit.' },
    tools: [
      { name: 'pipeline.compose', args: 'sklearn.compose', ms: 133 },
      { name: 'leakage.scan', args: 'target=churn', ms: 210 },
      { name: 'encode.plan', args: 'max_card=30', ms: 44 },
    ],
  },
  {
    id: 'n-selection',
    stage: 'selection',
    agent: 'Model Selector',
    role: 'search · ranking',
    action: 'Ran shortlist search over 7 candidates with recall-first ranking.',
    idleAction: 'Ranking candidate learners for the task.',
    input: 'candidates=7 · objective=recall · cv=5 · budget=12m',
    decision:
      'Advanced HistGradientBoosting, LogisticRegression(class_weight=balanced) and Calibrated SVM to full training. Dropped KNN (recall 0.61 on pilot) and rank-deficient LinearSVC.',
    confidence: 0.89,
    evidence: ['pilot.cv#3a90', 'search.space.v6', 'prior.telco.binary_gbdt'],
    verification: { status: 'VERIFIED', note: 'Pilot scores reproduced from cached folds.' },
    tools: [
      { name: 'search.pilot', args: 'n=7, folds=2', ms: 2_410 },
      { name: 'rank.by', args: 'metric=recall, tiebreak=auc', ms: 12 },
      { name: 'memory.query', args: 'problem=tabular-binary', ms: 66 },
    ],
  },
  {
    id: 'n-training',
    stage: 'training',
    agent: 'Trainer',
    role: 'fit · checkpoint',
    action: 'Fit shortlisted models on 5 stratified folds with early stopping.',
    idleAction: 'Fitting candidates on cross-validation folds.',
    input: 'HistGradientBoosting · LogisticRegression · CalibratedSVM · folds=5',
    decision:
      'HistGradientBoosting (max_iter=310, learning_rate=0.061, l2=1.8) won mean recall 0.871 ± 0.014. Checkpoint saved with seed 20260914.',
    confidence: 0.95,
    evidence: ['run.fold_metrics.csv', 'checkpoint://exp-0142/hgbt-v3', 'seed.register'],
    verification: { status: 'VERIFIED', note: 'Fold metrics independently re-fit on fold 3 — Δrecall 0.006.' },
    tools: [
      { name: 'fit.cv', args: 'model=hgbt, folds=5', ms: 148_000 },
      { name: 'checkpoint.save', args: 'format=onnx', ms: 420 },
      { name: 'resource.meter', args: 'cpu=4', ms: 9 },
    ],
  },
  {
    id: 'n-evaluation',
    stage: 'evaluation',
    agent: 'Evaluator',
    role: 'metrics · slices',
    action: 'Computed holdout metrics, calibration and slice-wise performance.',
    idleAction: 'Computing holdout metrics and slice diagnostics.',
    input: 'holdout=2,113 rows · threshold selected on OOF predictions',
    decision:
      'Threshold 0.42 maximizes recall subject to precision ≥ 0.60 → recall 0.864, precision 0.618, ROC-AUC 0.891. Recall dip of −0.07 found on tenure < 6 months slice.',
    confidence: 0.91,
    evidence: ['holdout.report#c41e', 'calibration.brier=0.117', 'slice.tenure_lt6'],
    verification: { status: 'UNVERIFIED', note: 'Slice dip flagged for verifier — sample size 214.' },
    tools: [
      { name: 'metrics.full', args: 'average=binary', ms: 96 },
      { name: 'threshold.optimize', args: 'constraint=precision>=0.60', ms: 58 },
      { name: 'slice.audit', args: 'dims=tenure,contract,region', ms: 302 },
    ],
  },
  {
    id: 'n-verification',
    stage: 'verification',
    agent: 'Verifier',
    role: 'claims · evidence',
    action: 'Re-derived headline metrics and cross-checked 14 emitted claims.',
    idleAction: 'Cross-checking agent claims against raw artifacts.',
    input: 'claims=14 · artifacts=6 · recompute=strict',
    decision:
      '13/14 claims verified by independent recompute. 1 claim downgraded (slice recall) to CONFLICTING — two evaluation paths disagreed by 0.05. Quarantined from final report.',
    confidence: 0.88,
    evidence: ['recompute.report#9b02', 'claim_ledger.exp-0142', 'dispute.slice_recall'],
    verification: { status: 'CONFLICTING', note: '1 conflicting claim quarantined; headline metrics unaffected.' },
    tools: [
      { name: 'recompute.metrics', args: 'strict=true', ms: 3_120 },
      { name: 'claim.verify', args: 'n=14', ms: 740 },
      { name: 'quarantine.put', args: 'claim=slice.recall.tenure_lt6', ms: 18 },
    ],
  },
  {
    id: 'n-pipeline',
    stage: 'pipeline',
    agent: 'Orchestrator',
    role: 'planner · router',
    action: 'Froze final pipeline, wrote reproducibility manifest and evidence trail.',
    idleAction: 'Assembling the final executable pipeline.',
    input: 'verified claims + champion checkpoint + frozen preprocessing graph',
    decision:
      'Pipeline autosage_telco_churn_v3 frozen: 9 steps, manifest signed, environment lock attached, replayable with 1 command.',
    confidence: 0.99,
    evidence: ['manifest.exp-0142.json', 'env.lock.conda', 'evidence.bundle'],
    verification: { status: 'VERIFIED', note: 'Dry-run replay on clean container matched metrics to 1e-6.' },
    tools: [
      { name: 'pipeline.freeze', args: 'format=sagemaker-free', ms: 260 },
      { name: 'manifest.sign', args: 'key=workspace', ms: 34 },
      { name: 'replay.dryrun', args: 'container=clean', ms: 5_400 },
    ],
  },
]

export const CHURN_RESULT: ExperimentResult = {
  bestPipeline: 'autosage_telco_churn_v3',
  pipelineSteps: [
    { index: 1, op: 'load', detail: 'telco_churn_2024.csv · sha256:4f19…c02a' },
    { index: 2, op: 'drop_columns', detail: 'customerID' },
    { index: 3, op: 'impute', detail: 'TotalCharges ← median (1397.4)' },
    { index: 4, op: 'encode', detail: 'OneHotEncoder(top=30, handle=other)' },
    { index: 5, op: 'scale', detail: 'StandardScaler on 9 numeric columns' },
    { index: 6, op: 'split', detail: 'StratifiedKFold(n=5, shuffle=true, seed=20260914)' },
    { index: 7, op: 'fit', detail: 'HistGradientBoostingClassifier' },
    { index: 8, op: 'calibrate', detail: 'isotonic · Brier 0.117' },
    { index: 9, op: 'threshold', detail: '0.42 (precision ≥ 0.60 constraint)' },
  ],
  metrics: [
    { name: 'Recall', value: 0.864, baseline: 0.712 },
    { name: 'Precision', value: 0.618, baseline: 0.54 },
    { name: 'ROC-AUC', value: 0.891, baseline: 0.83 },
    { name: 'F1', value: 0.721, baseline: 0.61 },
    { name: 'PR-AUC', value: 0.674, baseline: 0.55 },
    { name: 'Brier', value: 0.117, baseline: 0.16 },
  ],
  folds: [
    { fold: 1, trainRows: 5634, valRows: 1409, metric: 0.878, auc: 0.894, fitSec: 29.4 },
    { fold: 2, trainRows: 5634, valRows: 1409, metric: 0.855, auc: 0.887, fitSec: 28.9 },
    { fold: 3, trainRows: 5634, valRows: 1409, metric: 0.883, auc: 0.896, fitSec: 30.1 },
    { fold: 4, trainRows: 5635, valRows: 1408, metric: 0.862, auc: 0.889, fitSec: 29.7 },
    { fold: 5, trainRows: 5634, valRows: 1409, metric: 0.877, auc: 0.892, fitSec: 29.6 },
  ],
  featureImportance: [
    { feature: 'tenure', importance: 0.184, direction: 'negative' },
    { feature: 'Contract_Two year', importance: 0.151, direction: 'negative' },
    { feature: 'MonthlyCharges', importance: 0.132, direction: 'positive' },
    { feature: 'InternetService_Fiber optic', importance: 0.117, direction: 'positive' },
    { feature: 'TechSupport_No', importance: 0.081, direction: 'positive' },
    { feature: 'TotalCharges', importance: 0.064, direction: 'negative' },
    { feature: 'PaymentMethod_Electronic check', importance: 0.058, direction: 'positive' },
    { feature: 'OnlineSecurity_No', importance: 0.047, direction: 'positive' },
    { feature: 'Contract_Month-to-month', importance: 0.041, direction: 'positive' },
    { feature: 'num_support_tickets_90d', importance: 0.036, direction: 'positive' },
  ],
  datasetInsights: [
    { label: 'Rows × columns', value: '7,043 × 21' },
    { label: 'Target balance', value: '26.5% churn (1,869 positives)', note: 'stratified splits enforced' },
    { label: 'Missingness', value: '11 cells in TotalCharges (0.16%)' },
    { label: 'High-cardinality cats', value: '2 columns > 30 levels → grouped to other' },
    { label: 'Duplicate rows', value: '0 exact · 22 near-dup (kept)' },
    { label: 'Leakage probes', value: '2 / 2 passed', note: 'no post-outcome fields' },
    { label: 'Temporal coverage', value: '2023-01 → 2024-08' },
    { label: 'Drift vs baseline', value: 'PSI 0.03 (stable)', note: 'reference: telco_churn_2023' },
  ],
  reproducibility: [
    { label: 'Experiment ID', value: 'exp-0142' },
    { label: 'Seed', value: '20260914' },
    { label: 'Dataset hash', value: 'sha256:4f19a1c8…c02a' },
    { label: 'Code commit', value: 'a91f3ce (autosage-ml@0.9.4)' },
    { label: 'Environment', value: 'py3.11.9 · sklearn 1.5.2 · locked' },
    { label: 'Replay command', value: 'autosage replay exp-0142' },
    { label: 'Artifact digest', value: 'sha256:be04…91d7' },
    { label: 'Verified at', value: '2026-09-24 14:38 UTC' },
  ],
  leakageChecks: [
    { check: 'Target leakage scan', status: 'VERIFIED', note: 'No column derived post-outcome.' },
    { check: 'Train/holdout contamination', status: 'VERIFIED', note: 'Grouped split on customerID hash.' },
    { check: 'Feature availability at inference', status: 'VERIFIED', note: 'All 45 features computable at score time.' },
    { check: 'Temporal ordering', status: 'UNVERIFIED', note: 'Snapshot dataset — ordering assumed neutral.' },
  ],
}

const CHURN_LOGS: LogLine[] = [
  { id: 1, ts: '14:31:02.114', level: 'INFO', agent: 'Orchestrator', text: 'experiment exp-0142 accepted · verification=strict · budget=12m' },
  { id: 2, ts: '14:31:02.161', level: 'DECISION', agent: 'Orchestrator', text: 'task graph compiled → 9 stages, 8 agents' },
  { id: 3, ts: '14:31:03.402', level: 'INFO', agent: 'Data Scout', text: 'registry.search q="customer churn" k=5 → 5 hits in 118ms' },
  { id: 4, ts: '14:31:03.527', level: 'DECISION', agent: 'Data Scout', text: 'selected telco_churn_2024.csv (7043×21) · provenance ok' },
  { id: 5, ts: '14:31:03.554', level: 'VERIFY', agent: 'Verifier', text: 'artifact hash match sha256:4f19…c02a ✓' },
  { id: 6, ts: '14:31:04.210', level: 'INFO', agent: 'Profiler', text: 'profiling 21 columns · sampling=full' },
  { id: 7, ts: '14:31:04.856', level: 'METRIC', agent: 'Profiler', text: 'target base rate=0.2654 · missing cells=11 · dtypes=11c/9n/1d' },
  { id: 8, ts: '14:31:04.901', level: 'DECISION', agent: 'Profiler', text: 'stratified splitting required (base rate < 0.35)' },
  { id: 9, ts: '14:31:05.344', level: 'INFO', agent: 'Preprocessor', text: 'composing pipeline: impute → drop → one-hot → scale' },
  { id: 10, ts: '14:31:05.560', level: 'VERIFY', agent: 'Preprocessor', text: 'leakage.scan target=churn → 0 suspect columns (210ms)' },
  { id: 11, ts: '14:31:05.610', level: 'DECISION', agent: 'Preprocessor', text: 'feature schema frozen · n_features=45 · hash=9c21…77aa' },
  { id: 12, ts: '14:31:06.010', level: 'INFO', agent: 'Model Selector', text: 'memory.query tabular-binary → 6 prior experiments, 2 high-confidence priors' },
  { id: 13, ts: '14:31:08.431', level: 'METRIC', agent: 'Model Selector', text: 'pilot cv recall: hgbt=0.862 logreg=0.804 svm=0.791 knn=0.612' },
  { id: 14, ts: '14:31:08.470', level: 'DECISION', agent: 'Model Selector', text: 'shortlist → HistGradientBoosting, LogReg(balanced), CalibratedSVM' },
  { id: 15, ts: '14:31:08.505', level: 'WARN', agent: 'Model Selector', text: 'KNN dropped — pilot recall 0.612 below floor 0.70' },
  { id: 16, ts: '14:31:11.220', level: 'INFO', agent: 'Trainer', text: 'fit.cv model=hgbt folds=5 seed=20260914' },
  { id: 17, ts: '14:31:40.118', level: 'METRIC', agent: 'Trainer', text: 'fold 1/5 recall=0.878 auc=0.894 fit=29.4s' },
  { id: 18, ts: '14:32:09.004', level: 'METRIC', agent: 'Trainer', text: 'fold 2/5 recall=0.855 auc=0.887 fit=28.9s' },
  { id: 19, ts: '14:32:39.120', level: 'METRIC', agent: 'Trainer', text: 'fold 3/5 recall=0.883 auc=0.896 fit=30.1s' },
  { id: 20, ts: '14:33:08.880', level: 'METRIC', agent: 'Trainer', text: 'fold 4/5 recall=0.862 auc=0.889 fit=29.7s' },
  { id: 21, ts: '14:33:38.510', level: 'METRIC', agent: 'Trainer', text: 'fold 5/5 recall=0.877 auc=0.892 fit=29.6s' },
  { id: 22, ts: '14:33:39.004', level: 'DECISION', agent: 'Trainer', text: 'champion=hgbt mean recall=0.871 ± 0.014 · checkpoint saved' },
  { id: 23, ts: '14:33:39.410', level: 'INFO', agent: 'Evaluator', text: 'holdout n=2113 · threshold search with precision≥0.60' },
  { id: 24, ts: '14:33:39.490', level: 'METRIC', agent: 'Evaluator', text: 'threshold=0.42 recall=0.864 precision=0.618 auc=0.891' },
  { id: 25, ts: '14:33:39.792', level: 'WARN', agent: 'Evaluator', text: 'slice tenure<6m recall=0.794 (Δ-0.070) · n=214' },
  { id: 26, ts: '14:33:42.610', level: 'VERIFY', agent: 'Verifier', text: 'recompute.metrics strict → 13/14 claims reproduced' },
  { id: 27, ts: '14:33:43.350', level: 'WARN', agent: 'Verifier', text: 'CONFLICTING claim slice.recall.tenure_lt6 (Δ0.05) → quarantined' },
  { id: 28, ts: '14:33:43.402', level: 'VERIFY', agent: 'Verifier', text: 'headline metrics verified · bundle evidence.bundle#a91' },
  { id: 29, ts: '14:33:48.812', level: 'INFO', agent: 'Orchestrator', text: 'pipeline frozen autosage_telco_churn_v3 · 9 steps · signed' },
  { id: 30, ts: '14:33:48.901', level: 'VERIFY', agent: 'Orchestrator', text: 'clean-container replay matched Δmetric=2e-7 ✓' },
  { id: 31, ts: '14:33:48.944', level: 'INFO', agent: 'Orchestrator', text: 'experiment exp-0142 completed in 02m 46s · status=COMPLETED' },
]

export function nodesInState(state: AgentNode['state'], elapsed = true): AgentNode[] {
  return CHURN_NODES.map((spec, i) => ({
    ...spec,
    state,
    startedAt: state === 'idle' ? undefined : `14:31:${(2 + i * 3).toString().padStart(2, '0')}`,
    elapsedMs: state === 'idle' ? undefined : elapsed ? spec.tools.reduce((a, t) => a + t.ms, 0) : undefined,
  }))
}

export function churnExperiment(status: Experiment['status'] = 'completed'): Experiment {
  const done = status === 'completed'
  return {
    id: 'exp-0142',
    name: 'Telco churn · recall-first model search',
    prompt:
      'Predict customer churn using the uploaded dataset. Compare several models and optimize for recall.',
    status,
    dataset: 'telco_churn_2024.csv',
    target: 'churn',
    metric: 'recall',
    budget: '12 fit-min',
    verificationLevel: 'strict',
    model: 'HistGradientBoosting',
    runtime: done ? '2m 46s' : '—',
    verificationStatus: done ? 'VERIFIED' : 'UNVERIFIED',
    createdAt: '2026-09-24 14:31 UTC',
    owner: 'you',
    nodes: nodesInState(done ? 'done' : 'idle'),
    logs: done ? CHURN_LOGS : [],
    result: done ? CHURN_RESULT : undefined,
  }
}

export const EMPTY_RESULT_GUARD = undefined

const EXPERIMENT_SUMMARY: Omit<Experiment, 'nodes' | 'logs' | 'result'>[] = [
  {
    id: 'exp-0141',
    name: 'Loan default · calibrated probability model',
    prompt: 'Estimate probability of default on the LendingSphere application file; must be well calibrated.',
    status: 'completed',
    dataset: 'lending_applications_q3.csv',
    target: 'defaulted',
    metric: 'roc_auc',
    budget: '20 fit-min',
    verificationLevel: 'strict',
    model: 'XGBoost + isotonic',
    runtime: '6m 12s',
    verificationStatus: 'VERIFIED',
    createdAt: '2026-09-23 09:14 UTC',
    owner: 'm.okafor',
  },
  {
    id: 'exp-0140',
    name: 'Support ticket routing · multi-label',
    prompt: 'Route incoming tickets to the right team; allow multiple labels per ticket.',
    status: 'completed',
    dataset: 'tickets_2026H1.jsonl',
    target: 'teams',
    metric: 'f1_micro',
    budget: '30 fit-min',
    verificationLevel: 'standard',
    model: 'TF-IDF + OneVsRest(LogReg)',
    runtime: '11m 03s',
    verificationStatus: 'VERIFIED',
    createdAt: '2026-09-22 16:40 UTC',
    owner: 'you',
  },
  {
    id: 'exp-0139',
    name: 'Delivery ETA · regressor with drift guard',
    prompt: 'Predict delivery ETA in minutes; alert if feature drift exceeds PSI 0.2.',
    status: 'completed',
    dataset: 'deliveries_eu.parquet',
    target: 'eta_minutes',
    metric: 'mae',
    budget: '15 fit-min',
    verificationLevel: 'standard',
    model: 'LightGBM',
    runtime: '4m 58s',
    verificationStatus: 'CONFLICTING',
    createdAt: '2026-09-21 11:02 UTC',
    owner: 's.lindqvist',
  },
  {
    id: 'exp-0138',
    name: 'Fraud scoring · strict leakage audit',
    prompt: 'Score transactions for fraud. Verification must be strict — no leakage tolerated.',
    status: 'failed',
    dataset: 'txns_fraud_aug.csv',
    target: 'is_fraud',
    metric: 'precision_at_k',
    budget: '45 fit-min',
    verificationLevel: 'strict',
    model: '—',
    runtime: '1m 27s',
    verificationStatus: 'QUARANTINED',
    createdAt: '2026-09-20 08:33 UTC',
    owner: 'you',
  },
  {
    id: 'exp-0137',
    name: 'Readmission risk · recall-first',
    prompt: 'Predict 30-day readmission; optimize recall, report per-site slices.',
    status: 'completed',
    dataset: 'admissions_2025.csv',
    target: 'readmitted_30d',
    metric: 'recall',
    budget: '25 fit-min',
    verificationLevel: 'strict',
    model: 'CatBoost',
    runtime: '9m 41s',
    verificationStatus: 'VERIFIED',
    createdAt: '2026-09-19 13:57 UTC',
    owner: 'r.venkatesh',
  },
  {
    id: 'exp-0136',
    name: 'Churn baseline · logistic reference',
    prompt: 'Simple logistic baseline on the churn file for the quarterly report.',
    status: 'completed',
    dataset: 'telco_churn_2023.csv',
    target: 'churn',
    metric: 'recall',
    budget: '5 fit-min',
    verificationLevel: 'fast',
    model: 'LogisticRegression',
    runtime: '0m 51s',
    verificationStatus: 'VERIFIED',
    createdAt: '2026-09-18 10:21 UTC',
    owner: 'you',
  },
]

export const EXPERIMENTS: Experiment[] = [
  churnExperiment('completed'),
  ...EXPERIMENT_SUMMARY.map((e) => ({ ...e, nodes: nodesInState('idle', false), logs: [] })),
]

export function buildRunScript(exp: Experiment): { stage: StageId; logs: LogLine[] }[] {
  const script: { stage: StageId; logs: LogLine[] }[] = []
  let id = 1000
  for (const node of exp.nodes) {
    const lines: LogLine[] = [
      { id: id++, ts: '', level: 'INFO', agent: node.agent, text: `${node.stage} · ${node.action}` },
      { id: id++, ts: '', level: 'DECISION', agent: node.agent, text: node.decision },
    ]
    if (node.verification.status === 'VERIFIED') {
      lines.push({ id: id++, ts: '', level: 'VERIFY', agent: 'Verifier', text: `${node.evidence[0]} ✓ ${node.verification.note}` })
    } else if (node.verification.status !== 'UNVERIFIED') {
      lines.push({ id: id++, ts: '', level: 'WARN', agent: 'Verifier', text: `${node.verification.status}: ${node.verification.note}` })
    }
    script.push({ stage: node.stage, logs: lines })
  }
  return script
}

export function newExperiment(opts: {
  prompt: string
  dataset: string
  target: string
  metric: string
  budget: string
  verificationLevel: VerificationLevel
}): Experiment {
  const id = `exp-0${Math.floor(143 + Math.random() * 40)}`
  const title = opts.prompt.trim().split(/[.\n]/)[0]?.slice(0, 58) || 'Untitled experiment'
  return {
    id,
    name: title.charAt(0).toUpperCase() + title.slice(1),
    prompt: opts.prompt,
    status: 'draft',
    dataset: opts.dataset,
    target: opts.target,
    metric: opts.metric,
    budget: opts.budget,
    verificationLevel: opts.verificationLevel,
    model: '—',
    runtime: '—',
    verificationStatus: 'UNVERIFIED',
    createdAt: new Date().toISOString().slice(0, 16).replace('T', ' ') + ' UTC',
    owner: 'you',
    nodes: nodesInState('idle', false),
    logs: [],
  }
}
