import type { MemoryEntry } from '../lib/types'

export const MEMORY: MemoryEntry[] = [
  {
    id: 'mem-077',
    experiment: 'Telco churn · recall-first model search',
    problemType: 'Binary classification · imbalanced',
    datasetCharacteristics:
      '7k rows × 21 cols · 26.5% positive · 2 high-cardinality cats · 0.16% missing · snapshot (no time index)',
    successfulApproach:
      'Median impute → one-hot top-30 → HistGradientBoosting (lr 0.061, l2 1.8, iter 310) with isotonic calibration; threshold chosen under precision ≥ 0.60.',
    failedApproaches: [
      'KNN (k=25): recall floor 0.612 — distance metric collapses on one-hot space.',
      'Untuned XGBoost with default scale_pos_weight: overfit minority, precision 0.44.',
    ],
    confidence: 0.93,
    reusedCount: 6,
    lastUsed: '2026-09-24',
    whyUseful:
      'Same registry file family and identical target base rate. Prior runs show GBDT + threshold constraint reliably clears recall 0.85 here, while tree-free linear models plateau near 0.80. Reuse the frozen preprocessing graph to skip leakage re-probes.',
    tags: ['churn', 'tabular', 'imbalanced', 'threshold-tuning'],
  },
  {
    id: 'mem-074',
    experiment: 'Loan default · calibrated probability model',
    problemType: 'Binary classification · probability calibration',
    datasetCharacteristics:
      '48k rows × 34 cols · 7.9% positive · heavy missingness in 4 financial fields · strong skew on income',
    successfulApproach:
      'XGBoost with log-loss objective + isotonic calibration fit inside CV; report Brier and reliability curve alongside AUC.',
    failedApproaches: [
      'Platt scaling under-fit the mid-range (reliability gap 0.09 at p≈0.3).',
      'SMOTE before calibration: distorted probability mass, Brier 0.141 vs 0.102.',
    ],
    confidence: 0.9,
    reusedCount: 4,
    lastUsed: '2026-09-23',
    whyUseful:
      'Regulators here consume probabilities, not labels. Any future credit-risk task should start from this calibration pattern — never resample before calibrating.',
    tags: ['credit-risk', 'calibration', 'imbalanced'],
  },
  {
    id: 'mem-071',
    experiment: 'Support ticket routing · multi-label',
    problemType: 'Multi-label text classification',
    datasetCharacteristics:
      '31k tickets · 14 labels · mean 1.4 labels/ticket · heavy code-mixing · long-tailed labels (6 labels < 200 samples)',
    successfulApproach:
      'TF-IDF (1–2 grams, 60k features) + OneVsRest(LogReg) with per-label thresholds tuned on OOF; rare labels grouped into parent team.',
    failedApproaches: [
      'Fine-tuned transformer: +0.014 micro-F1 for 40× compute — rejected on budget.',
      'Global threshold 0.5: suppressed rare-label recall (0.41 → 0.63 after per-label tuning).',
    ],
    confidence: 0.87,
    reusedCount: 3,
    lastUsed: '2026-09-22',
    whyUseful:
      'Strong baseline for internal routing tasks with limited labels. Per-label thresholding is the single largest win — apply it before considering neural models.',
    tags: ['nlp', 'multi-label', 'sparse-text'],
  },
  {
    id: 'mem-069',
    experiment: 'Delivery ETA · regressor with drift guard',
    problemType: 'Regression · monitored production model',
    datasetCharacteristics:
      '1.2M rows × 27 cols · EU multi-market · seasonality + holiday effects · PSI drift vs prior quarter',
    successfulApproach:
      'LightGBM with rolling 8-week retrain; PSI guard at 0.2 wired into verification step; MAE reported per market.',
    failedApproaches: [
      'Linear regression with one-hot markets: MAE 11.8 vs 6.4 — interactions dominate.',
      'Single global model without market embedding: degraded 14% on Nordics.',
    ],
    confidence: 0.78,
    reusedCount: 2,
    lastUsed: '2026-09-21',
    whyUseful:
      'Only entry that pairs modeling with an explicit drift guard. Reuse when a model will be monitored — but note exp-0139 finished CONFLICTING on holiday-slice MAE, so re-validate slices.',
    tags: ['regression', 'drift', 'production'],
  },
  {
    id: 'mem-066',
    experiment: 'Fraud scoring · strict leakage audit',
    problemType: 'Binary classification · extreme imbalance',
    datasetCharacteristics:
      '2.4M transactions · 0.17% fraud · 3 suspect post-settlement columns · extreme class imbalance',
    successfulApproach: 'Not yet established — experiment quarantined pending upstream schema clarification.',
    failedApproaches: [
      'Direct fit including auth_score_v2: precision@k inflated ~2.1× (leakage).',
      'Undersampling to 1:50 without calibration: unusable probabilities.',
    ],
    confidence: 0.35,
    reusedCount: 1,
    lastUsed: '2026-09-20',
    whyUseful:
      'Negative knowledge: records exactly which columns caused leakage and which resampling schemes destroyed probability quality. Consult before touching fraud data.',
    tags: ['fraud', 'leakage', 'quarantined', 'negative-result'],
  },
  {
    id: 'mem-062',
    experiment: 'Readmission risk · recall-first',
    problemType: 'Binary classification · grouped entities',
    datasetCharacteristics:
      '86k admissions · 11.4% positive · 3 hospital sites · repeated patients (group id available) · strong site imbalance',
    successfulApproach:
      'CatBoost with patient-grouped CV; per-site recall reported; site fixed effects as categorical feature.',
    failedApproaches: [
      'Random K-fold (ignored patient groups): optimistic recall +0.05, rejected by verifier.',
      'Dropping site feature: masked label-policy differences between hospitals.',
    ],
    confidence: 0.89,
    reusedCount: 5,
    lastUsed: '2026-09-19',
    whyUseful:
      'Canonical example of why group-aware splitting matters. Any dataset with repeated entities should copy this CV scheme — verifier flags random K-fold as UNVERIFIED.',
    tags: ['healthcare', 'grouped-cv', 'imbalanced'],
  },
  {
    id: 'mem-058',
    experiment: 'Churn baseline · logistic reference',
    problemType: 'Binary classification · baseline',
    datasetCharacteristics: '6.9k rows × 20 cols · 26.1% positive · 2023 vintage of the telco file',
    successfulApproach: 'Regularized logistic regression (C=0.5) with one-hot encoding; serves as the reporting baseline.',
    failedApproaches: ['No feature interactions: recall 0.712 — kept deliberately as the floor to beat.'],
    confidence: 0.84,
    reusedCount: 8,
    lastUsed: '2026-09-18',
    whyUseful:
      'Cheap, deterministic reference point. Every telco-family experiment is compared against this baseline in the quarterly report — rerun it when the data vintage changes.',
    tags: ['baseline', 'churn', 'linear'],
  },
]
