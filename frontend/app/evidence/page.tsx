"use client";

import React from "react";
import {
  GitFork,
  ShieldCheck,
  CheckCircle2,
  FileSearch,
  Brain,
  Cpu,
  FlaskConical,
  ArrowDown,
  Layers,
  Sparkles,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface EvidenceTrailItem {
  step: string;
  agent: string;
  decision: string;
  claim: string;
  evidenceSource: string;
  evidenceType: string;
  timestamp: string;
  confidence: string;
  result: string;
  status: "verified";
  icon: React.ElementType;
}

const TRAIL_DATA: EvidenceTrailItem[] = [
  {
    step: "01",
    agent: "DatasetDiscoveryAgent",
    decision: "Accept dataset customer_churn.parquet (102,400 rows x 21 cols)",
    claim: "File contains complete column headers, valid UTF-8 encoding, and uncorrupted parquet dictionary.",
    evidenceSource: "pyarrow.parquet.ParquetFile header check",
    evidenceType: "File Header Schema Sniff",
    timestamp: "14:20:01",
    confidence: "100%",
    result: "Integrity Verified (21 valid columns, 0 corrupted rows)",
    status: "verified",
    icon: FileSearch,
  },
  {
    step: "02",
    agent: "ProfilerAgent",
    decision: "Enforce Stratified K-Fold and class weighting (12% churn rate)",
    claim: "Severe target imbalance will distort naive cross-validation and accuracy metrics.",
    evidenceSource: "ydata-profiling label distribution histogram",
    evidenceType: "Descriptive Statistical Metric",
    timestamp: "14:20:05",
    confidence: "99%",
    result: "Stratification parameter locked in pipeline config",
    status: "verified",
    icon: Cpu,
  },
  {
    step: "03",
    agent: "PreprocessorAgent",
    decision: "Deploy SimpleImputer(median) and TargetEncoder",
    claim: "Median imputation prevents distortion on skewed 'monthly_charges' (skew=+3.82).",
    evidenceSource: "AST Static Analysis of Pipeline Node (Zero Target Leak)",
    evidenceType: "Abstract Syntax Tree Invariant Check",
    timestamp: "14:20:12",
    confidence: "95%",
    result: "Pipeline AST Verified (fit strictly confined to train subset)",
    status: "verified",
    icon: Layers,
  },
  {
    step: "04",
    agent: "ModelSelectorAgent",
    decision: "Select LightGBMClassifier with Bayesian Hyperparameter Search",
    claim: "Gradient boosting with histogram binning delivers superior tabular F1-score within <15ms latency.",
    evidenceSource: "Verified Memory Vector #MEM-0941 + Empirical 5-Fold Evaluation",
    evidenceType: "Vector Memory Match + Benchmark Trial",
    timestamp: "14:21:40",
    confidence: "89%",
    result: "Val F1: 0.9124, Latency: 3.8ms (beats Logistic Reg F1: 0.7820)",
    status: "verified",
    icon: Brain,
  },
  {
    step: "05",
    agent: "VerificationEngine",
    decision: "Certify and commit final pipeline artifact bundle",
    claim: "Model strictly outperforms trivial majority baseline (+91.2% delta) and maintains train/val generalization.",
    evidenceSource: "Sandbox metric audit & DummyClassifier comparison",
    evidenceType: "Empirical Gatekeeper Verification",
    timestamp: "14:23:02",
    confidence: "99%",
    result: "Pipeline certified and committed to reproducibility registry",
    status: "verified",
    icon: ShieldCheck,
  },
];

export default function EvidencePage() {
  return (
    <AppShell>
      <div className="p-8 space-y-8 max-w-5xl mx-auto">
        <div className="border-b border-slate-900 pb-6">
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="verified">AUDITABLE REASONING CHAIN</Badge>
            <span className="text-xs font-mono text-slate-400">Run ID: #EXP-8941</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">
            Evidence Trail & Causal Lineage
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Trace the complete progression of decisions from raw data to final verified model: <span className="font-mono text-indigo-300">Agent &rarr; Decision &rarr; Evidence &rarr; Result</span>.
          </p>
        </div>

        {/* Trail Flow */}
        <div className="space-y-6">
          {TRAIL_DATA.map((item, idx) => {
            const Icon = item.icon;
            return (
              <React.Fragment key={item.step}>
                <div className="rounded-xl border border-slate-800 bg-slate-950 p-6 space-y-4 hover:border-slate-700 transition shadow-sm">
                  {/* Step Header */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-900 pb-3 font-mono text-xs">
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-950/80 text-indigo-400 border border-indigo-500/30">
                        <Icon size={16} />
                      </div>
                      <div>
                        <span className="font-semibold text-slate-100">
                          Step {item.step}: {item.agent}
                        </span>
                        <span className="text-slate-500 block text-[11px]">
                          Timestamp: {item.timestamp}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Badge variant="verified">Confidence: {item.confidence}</Badge>
                      <Badge variant="default">{item.evidenceType}</Badge>
                    </div>
                  </div>

                  {/* Decision & Claim */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div className="space-y-1">
                      <span className="font-mono text-[10px] uppercase text-slate-500">
                        Agent Decision
                      </span>
                      <p className="p-2.5 rounded bg-slate-900/60 border border-slate-800 text-slate-200 font-semibold">
                        {item.decision}
                      </p>
                    </div>

                    <div className="space-y-1">
                      <span className="font-mono text-[10px] uppercase text-slate-500">
                        Asserted Claim
                      </span>
                      <p className="p-2.5 rounded bg-slate-900/40 border border-slate-800/80 text-slate-300">
                        {item.claim}
                      </p>
                    </div>
                  </div>

                  {/* Evidence & Result */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono pt-1">
                    <div className="p-3 rounded-lg border border-indigo-500/20 bg-indigo-950/20 text-indigo-300">
                      <span className="text-[10px] uppercase text-slate-400 block mb-1">
                        Empirical Evidence Source
                      </span>
                      {item.evidenceSource}
                    </div>

                    <div className="p-3 rounded-lg border border-emerald-500/20 bg-emerald-950/20 text-emerald-300">
                      <span className="text-[10px] uppercase text-slate-400 block mb-1">
                        Verified Outcome
                      </span>
                      {item.result}
                    </div>
                  </div>
                </div>

                {/* Connector Arrow */}
                {idx < TRAIL_DATA.length - 1 && (
                  <div className="flex justify-center my-2 text-indigo-400/60">
                    <ArrowDown size={18} />
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </AppShell>
  );
}
