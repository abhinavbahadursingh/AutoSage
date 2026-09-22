"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Layers,
  ArrowRight,
  Clock,
  FileCheck2,
  Sparkles,
  GitPullRequest,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface VerificationItem {
  id: string;
  agent: string;
  stage: string;
  claim: string;
  status: "verified" | "warning" | "failed";
  confidence: string;
  evidenceSource: string;
  timestamp: string;
}

const VERIFICATION_RECORDS: VerificationItem[] = [
  {
    id: "VER-01",
    agent: "ModelSelectorAgent",
    stage: "Algorithm Viability",
    claim: "LightGBM histogram splitting is optimal for tabular data with high categorical cardinality.",
    status: "verified",
    confidence: "91%",
    evidenceSource: "Ke et al. LightGBM NeurIPS benchmark + Empirical Cross-Val Result",
    timestamp: "14:22:18",
  },
  {
    id: "VER-02",
    agent: "PreprocessorAgent",
    stage: "Target Leakage Invariant",
    claim: "Target column 'churned_status' excluded from feature matrix; no fit() leak on test splits.",
    status: "verified",
    confidence: "100%",
    evidenceSource: "Python AST Static Node Analysis",
    timestamp: "14:20:15",
  },
  {
    id: "VER-03",
    agent: "VerificationEngine",
    stage: "Trivial Baseline Dominance",
    claim: "Trained candidate F1 score (0.9124) significantly dominates majority class dummy baseline (0.0000).",
    status: "verified",
    confidence: "99%",
    evidenceSource: "DummyClassifier(strategy='most_frequent') Comparison",
    timestamp: "14:23:02",
  },
  {
    id: "VER-04",
    agent: "MLExperimentAgent",
    stage: "Container Sandbox Isolation",
    claim: "Process concluded without network requests, memory capped at 1.8GB / 4.0GB.",
    status: "verified",
    confidence: "100%",
    evidenceSource: "Docker Engine Daemon Exit Telemetry",
    timestamp: "14:22:45",
  },
];

export default function VerificationPage() {
  const [selectedRecord, setSelectedRecord] = useState<VerificationItem>(VERIFICATION_RECORDS[0]);

  return (
    <AppShell>
      <div className="p-8 space-y-8 max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-900 pb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="verified">VERIFICATION ENGINE ONLINE</Badge>
              <span className="text-xs font-mono text-slate-400">Mode: Single-Source Auditing</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">
              Verification Workspace & Evidence Gateway
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Every statistical decision and generated pipeline artifact is formally audited against empirical proof before acceptance.
            </p>
          </div>
        </div>

        {/* Verification Timeline / Lifecycle Map */}
        <div className="rounded-xl border border-slate-800 bg-slate-950 p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-900 pb-3">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-300">
              Audit Verification Lifecycle
            </span>
            <span className="text-xs font-mono text-emerald-400 font-semibold">
              4 / 4 Gates Passed
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs font-mono">
            {[
              { step: "01", name: "Claim Extracted", desc: "Agent emits explicit algorithmic rationale and empirical claim.", status: "ok" },
              { step: "02", name: "Evidence Found", desc: "AST, memory, or sandbox metric gathered as formal proof.", status: "ok" },
              { step: "03", name: "Evidence Checked", desc: "Rule engine runs boundary, leakage, and dominance tests.", status: "ok" },
              { step: "04", name: "Decision Certified", desc: "Artifact certified and committed to reproducible memory.", status: "ok" },
            ].map((st) => (
              <div
                key={st.step}
                className="p-3.5 rounded-lg border border-emerald-500/30 bg-emerald-950/20 space-y-1"
              >
                <div className="flex items-center justify-between text-emerald-400 font-bold">
                  <span>{st.step}. {st.name}</span>
                  <CheckCircle2 size={14} />
                </div>
                <p className="text-slate-300 font-sans text-[11px] leading-relaxed">
                  {st.desc}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Main Split: Records List vs Selected Evidence Inspection */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Records List */}
          <div className="space-y-3 md:col-span-2">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400 block">
              Audited Decisions & Invariants
            </span>

            {VERIFICATION_RECORDS.map((rec) => {
              const isSelected = selectedRecord.id === rec.id;
              return (
                <div
                  key={rec.id}
                  onClick={() => setSelectedRecord(rec)}
                  className={`p-4 rounded-xl border transition-all cursor-pointer space-y-2 ${
                    isSelected
                      ? "bg-slate-900 border-indigo-500 shadow-md ring-1 ring-indigo-500/40"
                      : "bg-slate-950/80 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs font-mono">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-indigo-300">{rec.id}</span>
                      <span className="text-slate-500">&bull;</span>
                      <span className="text-slate-300">{rec.stage}</span>
                    </div>
                    <Badge variant="verified">VERIFIED ({rec.confidence})</Badge>
                  </div>

                  <p className="text-xs text-slate-200 font-medium leading-relaxed">
                    {rec.claim}
                  </p>

                  <div className="flex items-center justify-between text-[11px] font-mono text-slate-500 pt-1 border-t border-slate-900">
                    <span>Source: {rec.agent}</span>
                    <span>{rec.timestamp}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Selected Evidence Detail Inspector */}
          <div className="space-y-4">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400 block">
              Evidence Audit Inspector
            </span>

            <Card className="border-indigo-500/30">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-1">
                  <span>Record {selectedRecord.id}</span>
                  <Badge variant="verified">VERIFIED</Badge>
                </div>
                <CardTitle className="text-sm font-semibold text-slate-100">
                  {selectedRecord.stage}
                </CardTitle>
                <CardDescription>
                  Emitted by {selectedRecord.agent}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-xs">
                <div className="space-y-1">
                  <span className="text-slate-500 font-mono text-[10px] uppercase">
                    Asserted Claim
                  </span>
                  <p className="text-slate-200 bg-slate-900/60 p-2.5 rounded border border-slate-800">
                    {selectedRecord.claim}
                  </p>
                </div>

                <div className="space-y-1">
                  <span className="text-slate-500 font-mono text-[10px] uppercase">
                    Empirical Proof Source
                  </span>
                  <p className="text-indigo-300 font-mono text-[11px] bg-indigo-950/30 p-2.5 rounded border border-indigo-500/30">
                    {selectedRecord.evidenceSource}
                  </p>
                </div>

                {/* Future Multi-Source Verification Expansion Concept */}
                <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/40 space-y-2">
                  <span className="font-mono text-[10px] text-slate-400 uppercase tracking-wider block">
                    Future Scope: Multi-Source Cross-Verification
                  </span>
                  <div className="text-[11px] text-slate-400 font-sans space-y-1">
                    <div>&bull; Source 1: Statistical Profiling (Passed)</div>
                    <div>&bull; Source 2: AST Static Analyzer (Passed)</div>
                    <div>&bull; Source 3: Independent LLM Audit (Ready)</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
