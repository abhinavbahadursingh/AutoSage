"use client";

import React, { useState } from "react";
import {
  BrainCircuit,
  Search,
  CheckCircle2,
  GitFork,
  Clock,
  Sparkles,
  Database,
  ArrowRight,
  ChevronRight,
  Layers,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface KnowledgeItem {
  id: string;
  claim: string;
  source: string;
  confidence: string;
  usedBy: string;
  lastUsed: string;
  taskType: string;
  status: "verified";
  empiricalGain: string;
  fingerprint: string;
}

const MEMORY_RECORDS: KnowledgeItem[] = [
  {
    id: "MEM-0941",
    claim: "Quantile transformation on skewed numerical features (skew > 3.0) lowers tree depth variance and boosts F1 by ~8%.",
    source: "Run #EXP-8420 (Telco Benchmark)",
    confidence: "94%",
    usedBy: "PreprocessorAgent",
    lastUsed: "12m ago",
    taskType: "Binary Classification",
    status: "verified",
    empiricalGain: "+8.4% Val F1 on 5-Fold Cross-Val",
    fingerprint: "cols=21, skew=3.82, missing=18.2%",
  },
  {
    id: "MEM-0940",
    claim: "Stratified K-Fold partitioning is mandatory when minority target representation is below 15% to avoid fold collapse.",
    source: "Run #EXP-8104 (Credit Scoring)",
    confidence: "99%",
    usedBy: "PipelinePreparationAgent",
    lastUsed: "2h ago",
    taskType: "Imbalanced Classification",
    status: "verified",
    empiricalGain: "Eliminated zero-positive fold anomalies",
    fingerprint: "target_imbalance=0.12, n_samples=100k",
  },
  {
    id: "MEM-0939",
    claim: "Target encoding outperforms one-hot encoding when categorical cardinality exceeds 40 unique values.",
    source: "Run #EXP-7940 (Fraud Detection)",
    confidence: "88%",
    usedBy: "ModelSelectorAgent",
    lastUsed: "1d ago",
    taskType: "High-Cardinality Tabular",
    status: "verified",
    empiricalGain: "Saved 42MB sparse RAM memory overhead",
    fingerprint: "max_cardinality=72, n_cat_cols=6",
  },
  {
    id: "MEM-0938",
    claim: "RobustScaler prevents gradient exploding in tree-based and linear estimators when outliers exceed 4% of samples.",
    source: "Run #EXP-7512 (Housing Valuation)",
    confidence: "92%",
    usedBy: "PreprocessorAgent",
    lastUsed: "3d ago",
    taskType: "Tabular Regression",
    status: "verified",
    empiricalGain: "14% lower RMSE on test split",
    fingerprint: "outlier_ratio=0.06, n_samples=50k",
  },
];

export default function MemoryPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedMemory, setSelectedMemory] = useState<KnowledgeItem>(MEMORY_RECORDS[0]);

  const filtered = MEMORY_RECORDS.filter(
    (m) =>
      m.claim.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.usedBy.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.taskType.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <AppShell>
      <div className="p-8 space-y-8 max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-900 pb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="verified">EXTRACTION-VERIFICATION MEMORY</Badge>
              <span className="text-xs font-mono text-slate-400">pgvector &bull; HNSW Cosine Index</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">
              Verified Knowledge & Memory Store
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              AutoSage continuously catalogs verified solutions, dataset fingerprints, and empirical rules to accelerate and improve future experiments.
            </p>
          </div>
        </div>

        {/* Search Bar */}
        <div className="relative max-w-xl">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search verified knowledge by claim, agent, or dataset fingerprint..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full rounded-md border border-slate-800 bg-slate-900/80 pl-9 pr-4 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
          />
        </div>

        {/* Knowledge Split: List vs Inspector */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Knowledge Table / List */}
          <div className="space-y-3 md:col-span-2">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400 block">
              Indexed Verified Experiences
            </span>

            {filtered.map((item) => {
              const isSelected = selectedMemory.id === item.id;
              return (
                <div
                  key={item.id}
                  onClick={() => setSelectedMemory(item)}
                  className={`p-4 rounded-xl border transition-all cursor-pointer space-y-2.5 ${
                    isSelected
                      ? "bg-slate-900 border-indigo-500 shadow-md ring-1 ring-indigo-500/40"
                      : "bg-slate-950/80 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs font-mono">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-indigo-300">{item.id}</span>
                      <span className="text-slate-500">&bull;</span>
                      <span className="text-slate-300">{item.taskType}</span>
                    </div>
                    <Badge variant="verified">Confidence: {item.confidence}</Badge>
                  </div>

                  <p className="text-xs text-slate-200 font-medium leading-relaxed">
                    "{item.claim}"
                  </p>

                  <div className="flex items-center justify-between text-[11px] font-mono text-slate-500 pt-1 border-t border-slate-900">
                    <span>Used By: <span className="text-slate-300">{item.usedBy}</span></span>
                    <span>Last Used: {item.lastUsed}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Selected Knowledge Inspector Panel */}
          <div className="space-y-4">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400 block">
              Memory Detail Inspector
            </span>

            <Card className="border-indigo-500/30">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-1">
                  <span>Vector Record {selectedMemory.id}</span>
                  <Badge variant="verified">VERIFIED</Badge>
                </div>
                <CardTitle className="text-sm font-semibold text-slate-100">
                  {selectedMemory.taskType}
                </CardTitle>
                <CardDescription>
                  Origin: {selectedMemory.source}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-xs font-mono">
                <div className="space-y-1">
                  <span className="text-slate-500 text-[10px] uppercase">
                    Verified Strategy Claim
                  </span>
                  <p className="text-slate-200 font-sans bg-slate-900/60 p-2.5 rounded border border-slate-800 leading-relaxed text-xs">
                    {selectedMemory.claim}
                  </p>
                </div>

                <div className="space-y-1">
                  <span className="text-slate-500 text-[10px] uppercase">
                    Empirical Performance Gain
                  </span>
                  <p className="text-emerald-400 bg-emerald-950/20 p-2 rounded border border-emerald-500/30 text-xs font-semibold">
                    {selectedMemory.empiricalGain}
                  </p>
                </div>

                <div className="space-y-1">
                  <span className="text-slate-500 text-[10px] uppercase">
                    Dataset Fingerprint Token
                  </span>
                  <p className="text-indigo-300 bg-indigo-950/20 p-2 rounded border border-indigo-500/30 text-[11px]">
                    {selectedMemory.fingerprint}
                  </p>
                </div>

                <div className="pt-2 text-[11px] text-slate-400 font-sans border-t border-slate-900">
                  When a researcher submits a new prompt with a similar dataset fingerprint, this verified strategy is automatically injected as few-shot exemplar context into the LangGraph state.
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
