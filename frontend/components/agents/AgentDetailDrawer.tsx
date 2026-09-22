"use client";

import React, { useState } from "react";
import { X, ShieldCheck, FileCode, CheckCircle2, Clock, Terminal, Copy } from "lucide-react";
import { AgentNodeData } from "./WorkflowGraph";
import { Badge } from "@/components/ui/Badge";
import { StatusIndicator } from "@/components/ui/StatusIndicator";

interface AgentDetailDrawerProps {
  node: AgentNodeData | null;
  onClose: () => void;
}

export function AgentDetailDrawer({ node, onClose }: AgentDetailDrawerProps) {
  const [activeTab, setActiveTab] = useState<"overview" | "evidence" | "decision" | "output">("overview");

  if (!node) return null;

  return (
    <aside className="fixed inset-y-0 right-0 z-40 w-full sm:w-[500px] border-l border-slate-800 bg-slate-950/95 backdrop-blur-md shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
      {/* Drawer Header */}
      <div className="flex items-center justify-between border-b border-slate-800 p-5">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-950/80 text-indigo-400 border border-indigo-500/30">
            <node.icon size={18} />
          </div>
          <div>
            <h3 className="font-semibold text-slate-100 text-sm">{node.name}</h3>
            <p className="text-xs text-slate-400 font-mono">{node.role}</p>
          </div>
        </div>

        <button
          onClick={onClose}
          className="rounded p-1.5 text-slate-400 hover:bg-slate-900 hover:text-slate-100 transition"
        >
          <X size={16} />
        </button>
      </div>

      {/* Meta Bar */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-900 bg-slate-900/40 text-xs font-mono">
        <div className="flex items-center gap-3">
          <StatusIndicator
            status={node.status === "completed" ? "verified" : node.status}
            label={node.status.toUpperCase()}
          />
          <span className="text-slate-500">|</span>
          <span className="text-slate-400 flex items-center gap-1">
            <Clock size={12} /> {node.runtime}
          </span>
        </div>
        {node.confidence && (
          <Badge variant="verified">Confidence: {node.confidence}</Badge>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800 px-5 text-xs font-mono">
        {(["overview", "decision", "evidence", "output"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`py-3 px-3 uppercase tracking-wider transition-colors border-b-2 font-medium ${
              activeTab === tab
                ? "border-indigo-500 text-indigo-300 font-semibold"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Drawer Content */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4 text-xs leading-relaxed">
        {activeTab === "overview" && (
          <div className="space-y-4">
            <div className="p-3.5 rounded-lg border border-slate-800 bg-slate-900/50 space-y-1.5">
              <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500 block">
                Primary Agent Objective
              </span>
              <p className="text-slate-200">{node.rationale || "Synthesize and execute verified domain transformation."}</p>
            </div>

            <div className="grid grid-cols-2 gap-3 font-mono">
              <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/30">
                <span className="text-slate-500 text-[10px] block">Evidence Sources</span>
                <span className="text-indigo-300 font-semibold text-sm">
                  {node.evidenceCount} Citations
                </span>
              </div>
              <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/30">
                <span className="text-slate-500 text-[10px] block">Verification Gate</span>
                <span className="text-emerald-400 font-semibold text-sm">PASSED</span>
              </div>
            </div>
          </div>
        )}

        {activeTab === "decision" && (
          <div className="space-y-3">
            <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500 block">
              Architectural Decision
            </span>
            <div className="p-3.5 rounded-lg border border-indigo-500/30 bg-indigo-950/20 text-indigo-200 font-mono">
              {node.decision || "LightGBM with Stratified Split & Target Encoding"}
            </div>

            <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500 block pt-2">
              Reasoning & Statistical Trade-off
            </span>
            <p className="text-slate-300">
              {node.rationale ||
                "Tabular structure exhibits severe categorical skew. LightGBM demonstrates robust histogram-based splitting with 4.2ms inference latency, comfortably satisfying production constraints."}
            </p>
          </div>
        )}

        {activeTab === "evidence" && (
          <div className="space-y-3">
            <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500 block">
              Empirical Citations & Proofs
            </span>
            <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/60 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-200">AST Split Invariant</span>
                <Badge variant="verified">Static Check: Pass</Badge>
              </div>
              <p className="text-slate-400 font-mono text-[11px]">
                sklearn.model_selection.StratifiedKFold invoked prior to any data transformation.
              </p>
            </div>

            <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/60 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-200">Historical Memory Match</span>
                <Badge variant="default">Cosine: 0.12</Badge>
              </div>
              <p className="text-slate-400 font-mono text-[11px]">
                Matched with verified experiment #EXP-8420 on 100k-row imbalanced churn task.
              </p>
            </div>
          </div>
        )}

        {activeTab === "output" && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">
                Generated Python Artifact
              </span>
              <button className="text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-mono text-[11px]">
                <Copy size={12} /> Copy Code
              </button>
            </div>
            <pre className="p-3.5 rounded-lg border border-slate-800 bg-slate-900 font-mono text-[11px] text-indigo-300 overflow-x-auto">
              {node.outputSnippet ||
                `# Preprocessing & Model Specification\nimport lightgbm as lgb\nfrom sklearn.pipeline import Pipeline\n\nmodel = lgb.LGBMClassifier(\n    n_estimators=300,\n    learning_rate=0.03,\n    class_weight='balanced',\n    random_state=42\n)`}
            </pre>
          </div>
        )}
      </div>
    </aside>
  );
}
