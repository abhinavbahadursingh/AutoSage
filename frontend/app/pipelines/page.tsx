"use client";

import React from "react";
import Link from "next/link";
import {
  Workflow,
  Download,
  Layers,
  CheckCircle2,
  Copy,
  ChevronRight,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface PipelineStage {
  id: string;
  name: string;
  type: string;
  spec: string;
  status: "verified";
}

const PIPELINE_STAGES: PipelineStage[] = [
  { id: "s1", name: "1. Raw Ingestion", type: "Data Source", spec: "customer_churn.parquet (102,400 x 21)", status: "verified" },
  { id: "s2", name: "2. Missing Imputer", type: "Preprocessing", spec: "SimpleImputer(strategy='median') on numericals", status: "verified" },
  { id: "s3", name: "3. Categorical Encoder", type: "Feature Transform", spec: "TargetEncoder(min_samples_leaf=10, smoothing=1.0)", status: "verified" },
  { id: "s4", name: "4. Scaler & Normalizer", type: "Scaling", spec: "RobustScaler() on tenure & charges", status: "verified" },
  { id: "s5", name: "5. Gradient Tree Model", type: "Estimator", spec: "LightGBMClassifier(n_estimators=300, lr=0.03)", status: "verified" },
  { id: "s6", name: "6. Probability Calibrator", type: "Inference", spec: "Isotonic Regression Probability Calibrator", status: "verified" },
];

export default function PipelinesPage() {
  return (
    <AppShell>
      <div className="p-8 space-y-8 max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-900 pb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="verified">PIPELINE ARTIFACT ONLINE</Badge>
              <span className="text-xs font-mono text-slate-400">Run ID: #EXP-8941</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">
              Reproducible Machine Learning Pipelines
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Visual topology of verified pipelines with production-ready sklearn-compatible serialization and Docker recipes.
            </p>
          </div>

          <Button variant="verified" size="sm" className="gap-2 text-xs">
            <Download size={15} />
            <span>Download Verified Bundle (.zip)</span>
          </Button>
        </div>

        {/* Visual Pipeline Stages */}
        <div className="rounded-xl border border-slate-800 bg-slate-950 p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-slate-900 pb-3">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-300">
              Pipeline Topology & Transformation Graph
            </span>
            <span className="text-xs font-mono text-emerald-400 font-semibold">
              Status: Verified & Export-Ready
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
            {PIPELINE_STAGES.map((stage, idx) => (
              <div
                key={stage.id}
                className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-950/20 space-y-2 relative"
              >
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-slate-400 text-[10px] uppercase">
                    {stage.type}
                  </span>
                  <CheckCircle2 size={13} className="text-emerald-400" />
                </div>
                <span className="font-semibold text-xs text-slate-100 block">
                  {stage.name}
                </span>
                <p className="text-[11px] font-mono text-slate-300 leading-tight">
                  {stage.spec}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Pipeline Details Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-mono uppercase tracking-wider text-slate-200">
                Pipeline Specifications & Invariants
              </CardTitle>
              <CardDescription>
                Formal properties enforced during model synthesis
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 font-mono text-xs">
              <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/40 space-y-1">
                <span className="text-slate-500 text-[10px] uppercase block">Scikit-Learn Interface</span>
                <span className="text-slate-200 font-semibold">sklearn.pipeline.Pipeline Compatible</span>
                <p className="text-[11px] font-sans text-slate-400 mt-1">
                  Full encapsulation: raw pandas DataFrame input directly yields calibrated class probabilities.
                </p>
              </div>

              <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/40 space-y-1">
                <span className="text-slate-500 text-[10px] uppercase block">Deterministic Seed Pinning</span>
                <span className="text-emerald-400 font-semibold">random_state=42 Locked</span>
                <p className="text-[11px] font-sans text-slate-400 mt-1">
                  Seeds fixed across Python core, NumPy RNG, and LightGBM backend for byte-for-byte reproducibility.
                </p>
              </div>

              <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/40 space-y-1">
                <span className="text-slate-500 text-[10px] uppercase block">Inference Budget</span>
                <span className="text-indigo-300 font-semibold">3.8 ms / Sample (Max P99: 7.2 ms)</span>
                <p className="text-[11px] font-sans text-slate-400 mt-1">
                  Lightweight histogram tree traversal suitable for production microservice deployment.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-sm font-mono uppercase tracking-wider text-slate-200">
                  Quick Inference Snippet
                </CardTitle>
                <CardDescription>
                  Two-line Python deployment invocation
                </CardDescription>
              </div>
              <button className="text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-mono text-xs">
                <Copy size={12} /> Copy
              </button>
            </CardHeader>
            <CardContent>
              <pre className="p-4 rounded-lg bg-slate-900 border border-slate-800 font-mono text-xs text-indigo-300 overflow-x-auto leading-relaxed">
{`import joblib
import pandas as pd

# Load serialized verified pipeline
pipeline = joblib.load("verified_pipeline.joblib")

# Pass raw un-preprocessed incoming customer records
incoming_df = pd.read_csv("new_customers.csv")
churn_probabilities = pipeline.predict_proba(incoming_df)[:, 1]

print(f"Predicted Churn Probability: {churn_probabilities[0]:.4f}")`}
              </pre>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
