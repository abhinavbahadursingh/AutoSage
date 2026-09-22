"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  FlaskConical,
  PlusCircle,
  Search,
  Filter,
  ArrowUpRight,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ChevronRight,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface ExperimentRow {
  id: string;
  name: string;
  dataset: string;
  task: string;
  model: string;
  metricLabel: string;
  metricValue: string;
  status: "verified" | "running" | "failed";
  created: string;
}

const EXPERIMENTS_DATA: ExperimentRow[] = [
  {
    id: "EXP-8941",
    name: "Customer Churn Retention Optimization",
    dataset: "customer_churn.parquet",
    task: "Binary Classification",
    model: "LightGBMClassifier",
    metricLabel: "F1 Score",
    metricValue: "0.9124",
    status: "running",
    created: "10m ago",
  },
  {
    id: "EXP-8940",
    name: "Credit Default Risk Evaluation",
    dataset: "credit_risk_sub.csv",
    task: "Binary Classification",
    model: "XGBoostClassifier",
    metricLabel: "ROC-AUC",
    metricValue: "0.8842",
    status: "verified",
    created: "2h ago",
  },
  {
    id: "EXP-8939",
    name: "Patient Readmission Anomaly Detection",
    dataset: "med_admissions.parquet",
    task: "Binary Classification",
    model: "RandomForestClassifier",
    metricLabel: "F1 Score",
    metricValue: "0.8410",
    status: "verified",
    created: "1d ago",
  },
  {
    id: "EXP-8938",
    name: "Metropolitan Housing Valuation",
    dataset: "housing_california.csv",
    task: "Regression",
    model: "RidgeCV",
    metricLabel: "RMSE",
    metricValue: "0.1240",
    status: "verified",
    created: "2d ago",
  },
  {
    id: "EXP-8937",
    name: "High-Frequency Transaction Fraud",
    dataset: "fraud_stream.csv",
    task: "Binary Classification",
    model: "HistGradientBoosting",
    metricLabel: "F1 Score",
    metricValue: "0.7190",
    status: "failed",
    created: "3d ago",
  },
];

export default function ExperimentsPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");

  const filtered = EXPERIMENTS_DATA.filter((exp) => {
    const matchesSearch =
      exp.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      exp.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      exp.dataset.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = filterStatus === "all" || exp.status === filterStatus;
    return matchesSearch && matchesStatus;
  });

  return (
    <AppShell>
      <div className="p-8 space-y-6 max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-900 pb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">
              Experiments Archive
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Complete historical record of natural-language ML formulations, verified models, and evaluation metrics.
            </p>
          </div>

          <Link href="/experiments/new">
            <Button size="sm" className="gap-1.5 text-xs">
              <PlusCircle size={14} />
              <span>New Experiment</span>
            </Button>
          </Link>
        </div>

        {/* Filter & Search Bar */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search
              size={15}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
            />
            <input
              type="text"
              placeholder="Search experiments by run ID, name, or dataset..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full rounded-md border border-slate-800 bg-slate-900/80 pl-9 pr-4 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div className="flex gap-2">
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-xs font-mono text-slate-300 focus:border-indigo-500 focus:outline-none"
            >
              <option value="all">Status: All</option>
              <option value="verified">Verified</option>
              <option value="running">Running</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>

        {/* Experiments Table */}
        <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950/70 shadow-sm">
          <table className="w-full text-left text-xs font-mono">
            <thead className="border-b border-slate-800 bg-slate-900/60 uppercase text-slate-400 text-[11px]">
              <tr>
                <th className="p-3.5">Run ID</th>
                <th className="p-3.5 font-sans">Experiment Title / Dataset</th>
                <th className="p-3.5">Task</th>
                <th className="p-3.5">Winning Model</th>
                <th className="p-3.5">Metric</th>
                <th className="p-3.5">Verification</th>
                <th className="p-3.5">Created</th>
                <th className="p-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-900">
              {filtered.map((row) => (
                <tr key={row.id} className="hover:bg-slate-900/40 transition">
                  <td className="p-3.5 font-semibold text-indigo-300">
                    <Link href={`/workflow`} className="hover:underline">
                      {row.id}
                    </Link>
                  </td>
                  <td className="p-3.5 font-sans">
                    <span className="font-semibold text-slate-100 block">
                      {row.name}
                    </span>
                    <span className="text-[11px] font-mono text-slate-500">
                      {row.dataset}
                    </span>
                  </td>
                  <td className="p-3.5 text-slate-400">{row.task}</td>
                  <td className="p-3.5 text-slate-200">{row.model}</td>
                  <td className="p-3.5 font-bold text-emerald-400">
                    {row.metricLabel}: {row.metricValue}
                  </td>
                  <td className="p-3.5">
                    <Badge
                      variant={
                        row.status === "verified"
                          ? "verified"
                          : row.status === "running"
                          ? "running"
                          : "error"
                      }
                    >
                      {row.status.toUpperCase()}
                    </Badge>
                  </td>
                  <td className="p-3.5 text-slate-500">{row.created}</td>
                  <td className="p-3.5 text-right font-sans">
                    <Link
                      href={`/results`}
                      className="text-xs text-indigo-400 hover:text-indigo-300 inline-flex items-center gap-1 font-medium"
                    >
                      Workspace <ChevronRight size={13} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  );
}
