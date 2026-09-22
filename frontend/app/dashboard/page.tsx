"use client";

import React from "react";
import Link from "next/link";
import {
  PlusCircle,
  Activity,
  ArrowUpRight,
  ShieldCheck,
  CheckCircle2,
  Cpu,
  Clock,
  ChevronRight,
  BarChart2,
  Layers,
  Database,
  Terminal,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { StatusIndicator } from "@/components/ui/StatusIndicator";

export default function DashboardPage() {
  return (
    <AppShell>
      <div className="p-8 space-y-8 max-w-7xl mx-auto">
        {/* Workspace Header Strip */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-900 pb-6">
          <div>
            <div className="inline-flex items-center gap-2 text-xs font-mono text-indigo-400 mb-1">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" />
              <span>RESEARCH WORKSPACE: DEEPMIND-BENCHMARK</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">
              AutoML Research Dashboard
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Monitor active multi-agent LangGraph runs, empirical verification gates, and knowledge lineage.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link href="/experiments">
              <Button variant="outline" size="sm">
                All Experiments
              </Button>
            </Link>
            <Link href="/experiments/new">
              <Button size="sm" className="gap-1.5">
                <PlusCircle size={15} />
                <span>Start Experiment</span>
              </Button>
            </Link>
          </div>
        </div>

        {/* Middle Section: Active Experiment Cockpit */}
        <div className="rounded-xl border border-indigo-500/30 bg-gradient-to-br from-indigo-950/40 via-slate-950 to-slate-950 p-6 shadow-xl space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="running">EXP-8941</Badge>
                <span className="font-semibold text-slate-100 text-base">
                  Customer Churn & Retention Optimization
                </span>
                <span className="text-xs text-slate-500 font-mono">
                  (customer_churn.parquet)
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Active Node: <span className="font-mono text-indigo-300 font-medium">ModelSelectorAgent</span> &bull; 
                Evaluating LightGBM Bayesian hyperparameter tuning across 5 stratified folds
              </p>
            </div>

            <div className="flex items-center gap-4">
              <div className="text-right font-mono text-xs">
                <div className="text-slate-400">Container RAM</div>
                <div className="text-slate-200 font-semibold">1.8 GB / 4.0 GB</div>
              </div>
              <div className="text-right font-mono text-xs">
                <div className="text-slate-400">Elapsed Time</div>
                <div className="text-slate-200 font-semibold">02m 44s</div>
              </div>
              <Link href="/experiments/EXP-8941/workflow">
                <Button size="sm" variant="primary" className="gap-1.5">
                  <span>Open Live Graph</span>
                  <ArrowUpRight size={14} />
                </Button>
              </Link>
            </div>
          </div>

          {/* Workflow Step Bar */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs font-mono text-slate-400">
              <span>Workflow Stage (Node 4 of 6)</span>
              <span>65% Progress</span>
            </div>
            <div className="h-2 w-full rounded-full bg-slate-900 overflow-hidden">
              <div className="h-full bg-gradient-to-r from-indigo-500 to-emerald-500 rounded-full w-[65%]" />
            </div>

            <div className="grid grid-cols-6 gap-2 pt-2 text-[11px] font-mono text-center">
              <div className="text-emerald-400 font-medium">1. Discovery (OK)</div>
              <div className="text-emerald-400 font-medium">2. Profiler (OK)</div>
              <div className="text-emerald-400 font-medium">3. Preprocessor (OK)</div>
              <div className="text-indigo-300 font-semibold animate-pulse">4. Model Select (*)</div>
              <div className="text-slate-500">5. Experimenter</div>
              <div className="text-slate-500">6. Verification</div>
            </div>
          </div>
        </div>

        {/* Middle Dual Grid: Agent Status & Verification Gate */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Agent Status Registry */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-sm font-mono uppercase tracking-wider text-slate-200">
                  Agent Mesh Status
                </CardTitle>
                <CardDescription>
                  LangGraph asynchronous runtime nodes
                </CardDescription>
              </div>
              <Link href="/agents" className="text-xs text-indigo-400 hover:underline">
                View Spec
              </Link>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                { name: "Dataset Discovery Agent", status: "verified", task: "Schema sniffer & encoding parsed" },
                { name: "Profiler Agent", status: "verified", task: "Statistical skewness & missingness computed" },
                { name: "Preprocessor Agent", status: "verified", task: "SimpleImputer + TargetEncoder code built" },
                { name: "Model Selector Agent", status: "running", task: "Optimizing LightGBM parameters" },
                { name: "ML Experiment Agent", status: "pending", task: "Awaiting container dispatch" },
                { name: "Verification Engine", status: "pending", task: "AST & metric sanity rules queued" },
              ].map((agent) => (
                <div
                  key={agent.name}
                  className="flex items-center justify-between p-2.5 rounded-md border border-slate-900 bg-slate-900/40 text-xs"
                >
                  <div className="space-y-0.5">
                    <span className="font-medium text-slate-200">{agent.name}</span>
                    <p className="text-[11px] text-slate-400">{agent.task}</p>
                  </div>
                  <StatusIndicator
                    status={agent.status as any}
                    label={agent.status.toUpperCase()}
                  />
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Verification Status & Evidence Snapshot */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="text-sm font-mono uppercase tracking-wider text-slate-200">
                  Active Verification Gateway
                </CardTitle>
                <CardDescription>
                  Automated empirical rule enforcement
                </CardDescription>
              </div>
              <Badge variant="verified">100% Passed</Badge>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/20 p-3 space-y-2">
                <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400">
                  <ShieldCheck size={16} />
                  <span>Preprocessor AST Rule Passed</span>
                </div>
                <p className="text-[11px] text-slate-300 leading-relaxed font-mono">
                  AST validator verified that TargetEncoder was fit exclusively on train fold X_tr. Test data transformation is purely passive. Zero leakage.
                </p>
              </div>

              <div className="space-y-2 text-xs font-mono">
                <div className="flex justify-between text-slate-400">
                  <span>Trivial Majority Baseline:</span>
                  <span className="text-slate-200">0.5000 F1</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Current Candidate Estimate:</span>
                  <span className="text-emerald-400 font-semibold">0.9124 F1 (+82.4% over baseline)</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Security Sandbox Constraints:</span>
                  <span className="text-slate-200">--network none, read-only</span>
                </div>
              </div>

              <Link href="/verification" className="block pt-2">
                <Button variant="outline" size="sm" className="w-full text-xs">
                  Inspect All Verification Logs
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>

        {/* Lower Section: Recent Experiments & Evidence */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-200">
              Recent Verified Experiments
            </h2>
            <Link href="/experiments" className="text-xs text-indigo-400 hover:underline">
              View All Experiments
            </Link>
          </div>

          <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950/70">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-800 bg-slate-900/60 font-mono uppercase text-slate-400">
                <tr>
                  <th className="p-3">Run ID</th>
                  <th className="p-3">Problem / Dataset</th>
                  <th className="p-3">Selected Model</th>
                  <th className="p-3">Primary Metric</th>
                  <th className="p-3">Verification</th>
                  <th className="p-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-900 font-mono">
                {[
                  {
                    id: "EXP-8940",
                    task: "Credit Risk Scoring (credit.parquet)",
                    model: "XGBoostClassifier",
                    metric: "ROC-AUC: 0.8842",
                    status: "verified",
                  },
                  {
                    id: "EXP-8939",
                    task: "Synthetic Medical Anomaly (med_data.csv)",
                    model: "RandomForestClassifier",
                    metric: "F1: 0.8410",
                    status: "verified",
                  },
                  {
                    id: "EXP-8938",
                    task: "House Price Regression (housing.csv)",
                    model: "RidgeCV",
                    metric: "RMSE: 0.1240",
                    status: "verified",
                  },
                ].map((row) => (
                  <tr key={row.id} className="hover:bg-slate-900/40 transition">
                    <td className="p-3 font-semibold text-indigo-300">{row.id}</td>
                    <td className="p-3 text-slate-200 font-sans">{row.task}</td>
                    <td className="p-3 text-slate-300">{row.model}</td>
                    <td className="p-3 font-semibold text-emerald-400">{row.metric}</td>
                    <td className="p-3">
                      <Badge variant="verified">VERIFIED</Badge>
                    </td>
                    <td className="p-3">
                      <Link
                        href={`/results`}
                        className="text-indigo-400 hover:text-indigo-300 inline-flex items-center gap-1"
                      >
                        Results <ChevronRight size={12} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
