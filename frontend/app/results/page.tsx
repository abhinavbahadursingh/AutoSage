"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Download,
  ShieldCheck,
  CheckCircle2,
  BarChart2,
  FileCode,
  Copy,
  ChevronRight,
  Sparkles,
  Layers,
  ArrowUpRight,
  GitFork,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface ModelBenchmark {
  model: string;
  f1: number;
  accuracy: number;
  auc: number;
  trainingTime: string;
  isWinner?: boolean;
}

const BENCHMARKS: ModelBenchmark[] = [
  { model: "LightGBMClassifier (Selected)", f1: 0.9124, accuracy: 0.9341, auc: 0.9542, trainingTime: "14.2s", isWinner: true },
  { model: "XGBoostClassifier", f1: 0.9048, accuracy: 0.9280, auc: 0.9481, trainingTime: "28.5s" },
  { model: "RandomForestClassifier", f1: 0.8650, accuracy: 0.8920, auc: 0.9120, trainingTime: "18.1s" },
  { model: "LogisticRegression (L2)", f1: 0.7820, accuracy: 0.8410, auc: 0.8204, trainingTime: "3.2s" },
  { model: "DummyClassifier (Majority)", f1: 0.0000, accuracy: 0.8800, auc: 0.5000, trainingTime: "0.1s" },
];

export default function ResultsPage() {
  const [activeTab, setActiveTab] = useState<"overview" | "comparison" | "pipeline" | "reproducibility">("overview");

  return (
    <AppShell>
      <div className="p-8 space-y-8 max-w-7xl mx-auto">
        {/* Header Strip */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-900 pb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="verified">EMPIRICALLY VERIFIED</Badge>
              <span className="text-xs font-mono text-slate-400">Run ID: #EXP-8941</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">
              Experiment Results & Model Certification
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Customer Churn Classification &bull; LightGBM with Bayesian Tuning &bull; Stratified 5-Fold Cross-Validation
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link href="/evidence">
              <Button variant="outline" size="sm" className="gap-1.5 text-xs">
                <GitFork size={14} />
                <span>Evidence Trail</span>
              </Button>
            </Link>
            <Button variant="verified" size="sm" className="gap-1.5 text-xs">
              <Download size={14} />
              <span>Download Pipeline Package (.zip)</span>
            </Button>
          </div>
        </div>

        {/* Top Key Metrics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4 font-mono">
          {[
            { label: "F1 Score (Macro)", value: "0.9124", delta: "+41.2% vs Dummy", highlight: true },
            { label: "ROC-AUC Score", value: "0.9542", delta: "Optimal Cutoff: 0.42" },
            { label: "Precision", value: "0.8940", delta: "Low False Positives" },
            { label: "Recall", value: "0.9318", delta: "Captured 93% Churn" },
            { label: "Balanced Accuracy", value: "0.9018", delta: "Controls Imbalance" },
            { label: "Inference Latency", value: "3.8 ms", delta: "P99: 7.2 ms" },
          ].map((metric) => (
            <div
              key={metric.label}
              className={`p-4 rounded-lg border ${
                metric.highlight
                  ? "border-emerald-500/40 bg-emerald-950/20 shadow-md shadow-emerald-500/5"
                  : "border-slate-800 bg-slate-900/40"
              }`}
            >
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block">
                {metric.label}
              </span>
              <div
                className={`text-xl font-bold mt-1 ${
                  metric.highlight ? "text-emerald-400" : "text-slate-100"
                }`}
              >
                {metric.value}
              </div>
              <span className="text-[10px] text-slate-500 block mt-0.5">
                {metric.delta}
              </span>
            </div>
          ))}
        </div>

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-800 text-xs font-mono">
          {[
            { id: "overview", label: "Research Overview" },
            { id: "comparison", label: "Model Benchmark Comparison" },
            { id: "pipeline", label: "Exportable Pipeline Code" },
            { id: "reproducibility", label: "Reproducibility Bundle" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`py-3 px-4 font-medium uppercase tracking-wider transition-colors border-b-2 ${
                activeTab === tab.id
                  ? "border-indigo-500 text-indigo-300 font-semibold"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab 1: Overview & Curves */}
        {activeTab === "overview" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Feature Attribution (SHAP) */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-mono uppercase tracking-wider text-slate-200">
                  Feature Importance Attribution
                </CardTitle>
                <CardDescription>
                  Mean absolute SHAP value impact on churn prediction
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 font-mono text-xs">
                {[
                  { feature: "contract_duration (months)", importance: 0.38, bar: "w-[85%]" },
                  { feature: "monthly_charges ($)", importance: 0.26, bar: "w-[65%]" },
                  { feature: "total_tenure_months", importance: 0.19, bar: "w-[50%]" },
                  { feature: "support_tickets_count", importance: 0.12, bar: "w-[35%]" },
                  { feature: "payment_method_electronic", importance: 0.05, bar: "w-[15%]" },
                ].map((item) => (
                  <div key={item.feature} className="space-y-1">
                    <div className="flex justify-between text-slate-300 text-[11px]">
                      <span>{item.feature}</span>
                      <span className="text-indigo-400 font-semibold">+{item.importance}</span>
                    </div>
                    <div className="h-1.5 w-full bg-slate-900 rounded-full overflow-hidden">
                      <div className={`h-full bg-indigo-500 rounded-full ${item.bar}`} />
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Verification Invariants Proof */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-mono uppercase tracking-wider text-slate-200">
                  Verification Certification
                </CardTitle>
                <CardDescription>
                  Empirical tests executed before pipeline approval
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-xs">
                <div className="flex items-start gap-3 p-3 rounded-lg border border-emerald-500/20 bg-emerald-950/20">
                  <CheckCircle2 size={16} className="text-emerald-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-emerald-300 block">
                      Target Leakage Invariant: PASSED
                    </span>
                    <p className="text-slate-300 font-mono text-[11px] mt-0.5">
                      Target column 'churned_status' was excluded from feature matrix X. No target tokens appeared in transformer .fit() AST nodes.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 p-3 rounded-lg border border-emerald-500/20 bg-emerald-950/20">
                  <CheckCircle2 size={16} className="text-emerald-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-emerald-300 block">
                      Overfitting Delta Threshold: PASSED
                    </span>
                    <p className="text-slate-300 font-mono text-[11px] mt-0.5">
                      Train F1 (0.9320) vs Val F1 (0.9124) difference is 0.0196, comfortably below the 0.25 ceiling.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 p-3 rounded-lg border border-emerald-500/20 bg-emerald-950/20">
                  <CheckCircle2 size={16} className="text-emerald-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold text-emerald-300 block">
                      Dummy Baseline Dominance: PASSED
                    </span>
                    <p className="text-slate-300 font-mono text-[11px] mt-0.5">
                      LightGBM (0.9124) outperforms the majority class dummy baseline (0.0000) by +91.2%.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Tab 2: Model Benchmark Table */}
        {activeTab === "comparison" && (
          <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950">
            <table className="w-full text-left text-xs font-mono">
              <thead className="border-b border-slate-800 bg-slate-900/60 uppercase text-slate-400">
                <tr>
                  <th className="p-3.5">Model Architecture</th>
                  <th className="p-3.5">F1 (Macro)</th>
                  <th className="p-3.5">Accuracy</th>
                  <th className="p-3.5">ROC-AUC</th>
                  <th className="p-3.5">Training Time</th>
                  <th className="p-3.5">Verification</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-900">
                {BENCHMARKS.map((row) => (
                  <tr
                    key={row.model}
                    className={`hover:bg-slate-900/40 transition ${
                      row.isWinner ? "bg-emerald-950/20" : ""
                    }`}
                  >
                    <td className="p-3.5 font-semibold text-slate-200 flex items-center gap-2">
                      {row.isWinner && <Badge variant="verified">WINNER</Badge>}
                      <span>{row.model}</span>
                    </td>
                    <td className="p-3.5 font-bold text-emerald-400">{row.f1.toFixed(4)}</td>
                    <td className="p-3.5 text-slate-300">{row.accuracy.toFixed(4)}</td>
                    <td className="p-3.5 text-slate-300">{row.auc.toFixed(4)}</td>
                    <td className="p-3.5 text-slate-400">{row.trainingTime}</td>
                    <td className="p-3.5">
                      {row.isWinner ? (
                        <Badge variant="verified">CERTIFIED</Badge>
                      ) : (
                        <Badge variant="pending">SUB-OPTIMAL</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 3: Exportable Pipeline Code */}
        {activeTab === "pipeline" && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-sm font-mono uppercase tracking-wider text-slate-200">
                  standalone_pipeline.py
                </CardTitle>
                <CardDescription>
                  Production-ready self-contained Python script
                </CardDescription>
              </div>
              <button className="text-indigo-400 hover:text-indigo-300 flex items-center gap-1 text-xs font-mono">
                <Copy size={13} /> Copy All
              </button>
            </CardHeader>
            <CardContent>
              <pre className="p-4 rounded-lg bg-slate-900 border border-slate-800 font-mono text-xs text-indigo-300 overflow-x-auto leading-relaxed">
{`# AutoSage Verified AutoML Pipeline
# Problem: Customer Churn Classification
# Generated on: 2026-09-22 | Verified by: VerificationEngine

import sys
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from category_encoders import TargetEncoder

def build_pipeline():
    numeric_imputer = SimpleImputer(strategy="median")
    categorical_encoder = TargetEncoder(min_samples_leaf=10, smoothing=1.0)
    
    model = lgb.LGBMClassifier(
        n_estimators=300,
        learning_rate=0.03,
        max_depth=6,
        class_weight="balanced",
        random_state=42
    )
    
    return Pipeline([
        ("imputer", numeric_imputer),
        ("encoder", categorical_encoder),
        ("classifier", model)
    ])

if __name__ == "__main__":
    df = pd.read_parquet("customer_churn.parquet")
    X = df.drop(columns=["churned_status", "customer_id"])
    y = df["churned_status"]
    
    pipeline = build_pipeline()
    pipeline.fit(X, y)
    print("Pipeline successfully trained and verified.")`}
              </pre>
            </CardContent>
          </Card>
        )}

        {/* Tab 4: Reproducibility Bundle */}
        {activeTab === "reproducibility" && (
          <div className="space-y-4 text-xs font-mono">
            <div className="p-4 rounded-lg border border-slate-800 bg-slate-900/50 space-y-2">
              <span className="font-semibold text-slate-200 block text-sm">
                Reproducibility Guarantee & Docker Spec
              </span>
              <p className="text-slate-400 font-sans">
                Every package contains exact package hashes, seed controls (random_state=42), and the base Dockerfile digest used during the sandboxed run.
              </p>
              <div className="mt-3 p-3 rounded bg-slate-950 border border-slate-800 text-slate-300">
                <code>docker run --rm -v $(pwd):/workspace autosage-runner:latest python /workspace/standalone_pipeline.py</code>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
