"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  FileSearch,
  BarChart2,
  Cpu,
  Brain,
  FlaskConical,
  ShieldCheck,
  CheckCircle2,
  Clock,
  ArrowRight,
  Terminal,
  Activity,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { WorkflowGraph, AgentNodeData } from "@/components/agents/WorkflowGraph";
import { AgentDetailDrawer } from "@/components/agents/AgentDetailDrawer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

const INITIAL_NODES: AgentNodeData[] = [
  {
    id: "discovery",
    name: "Dataset Discovery",
    role: "Schema & File Inspection",
    status: "completed",
    runtime: "1.2s",
    confidence: "100%",
    evidenceCount: 1,
    decision: "Validated CSV delimiter, UTF-8 encoding, and Parquet metadata.",
    rationale: "File header sniffer detected 21 columns with zero encoding corruption.",
    outputSnippet: '{"rows": 102400, "cols": 21, "file_size_mb": 14.2, "format": "parquet"}',
    icon: FileSearch,
  },
  {
    id: "profiler",
    name: "Profiler Agent",
    role: "Statistical Profiling",
    status: "completed",
    runtime: "5.8s",
    confidence: "98%",
    evidenceCount: 2,
    decision: "Identified severe 12:88 imbalance and right-skew on monthly charges.",
    rationale: "Statistical profiling recommends median imputation and stratification.",
    outputSnippet: '{"target_distribution": {"0": 0.88, "1": 0.12}, "missing_charges": 0.182}',
    icon: BarChart2,
  },
  {
    id: "preprocessor",
    name: "Preprocessor Agent",
    role: "AST Code Synthesis",
    status: "completed",
    runtime: "8.4s",
    confidence: "95%",
    evidenceCount: 3,
    decision: "Synthesized SimpleImputer(median) and TargetEncoder.",
    rationale: "High cardinality in categorical columns dictates target encoding over one-hot.",
    outputSnippet: 'pipeline = Pipeline([\n    ("impute", SimpleImputer(strategy="median")),\n    ("encode", TargetEncoder())\n])',
    icon: Cpu,
  },
  {
    id: "model_selector",
    name: "Model Selector",
    role: "Algorithm Hypothesizer",
    status: "running",
    runtime: "14.2s",
    confidence: "89%",
    evidenceCount: 4,
    decision: "Selected LightGBM with Bayesian tuning over 5 stratified folds.",
    rationale: "LightGBM offers optimal tabular split efficiency under 15ms latency.",
    outputSnippet: 'clf = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, class_weight="balanced")',
    icon: Brain,
  },
  {
    id: "experimenter",
    name: "ML Experimenter",
    role: "Docker Sandbox Runner",
    status: "pending",
    runtime: "--",
    evidenceCount: 0,
    decision: "Awaiting container dispatch (--network none, 4GB RAM).",
    rationale: "Will execute isolated training script and capture metrics.json.",
    icon: FlaskConical,
  },
  {
    id: "verifier",
    name: "Verification Engine",
    role: "Empirical Gatekeeper",
    status: "pending",
    runtime: "--",
    evidenceCount: 0,
    decision: "Awaiting empirical metric logs for leakage and triviality validation.",
    rationale: "Will assert bounds, overfitting threshold (<=0.25), and dummy baseline dominance.",
    icon: ShieldCheck,
  },
];

const TIMELINE_LOGS = [
  { time: "14:20:01", agent: "Discovery", status: "completed", msg: "Validated customer_churn.parquet (102,400 rows, 21 cols)" },
  { time: "14:20:05", agent: "Profiler", status: "completed", msg: "Detected 18.2% missingness in 'monthly_charges' & 12% target imbalance" },
  { time: "14:20:12", agent: "Preprocessor", status: "completed", msg: "Synthesized leak-free transformation pipeline (SimpleImputer + TargetEncoder)" },
  { time: "14:20:15", agent: "Verification", status: "completed", msg: "AST Security Passed: Zero forbidden imports or eval() calls detected" },
  { time: "14:21:40", agent: "ModelSelector", status: "running", msg: "Running Bayesian Hyperparameter Optimization on LightGBM (Iteration 14/20)..." },
];

export default function WorkflowPage() {
  const [nodes, setNodes] = useState<AgentNodeData[]>(INITIAL_NODES);
  const [selectedNode, setSelectedNode] = useState<AgentNodeData | null>(INITIAL_NODES[3]);

  return (
    <AppShell>
      <div className="p-8 space-y-6 max-w-7xl mx-auto">
        {/* Header Strip */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-900 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Badge variant="running">RUNNING</Badge>
              <h1 className="text-xl font-bold tracking-tight text-slate-100">
                Run #EXP-8941: Multi-Agent Orchestration Mesh
              </h1>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-1">
              LangGraph StateGraph &bull; Active: ModelSelectorAgent &bull; Elapsed: 02m 44s
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link href="/results">
              <Button variant="outline" size="sm" className="gap-1.5 text-xs">
                <span>View Interim Results</span>
                <ArrowRight size={13} />
              </Button>
            </Link>
          </div>
        </div>

        {/* The Graph */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span className="flex items-center gap-1.5">
              <Activity size={13} className="text-indigo-400" />
              <span>Multi-Agent State Transition Graph</span>
            </span>
            <span>Cycles Enabled (Autonomous Self-Correction Gate)</span>
          </div>

          <WorkflowGraph
            nodes={nodes}
            selectedNodeId={selectedNode?.id || ""}
            onSelectNode={(node) => setSelectedNode(node)}
          />
        </div>

        {/* Execution Timeline Under Graph */}
        <div className="rounded-xl border border-slate-800 bg-slate-950 p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-900 pb-3">
            <div className="flex items-center gap-2">
              <Terminal size={15} className="text-indigo-400" />
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-200">
                Live Execution Timeline
              </span>
            </div>
            <span className="text-[11px] font-mono text-slate-500">
              Real-time SSE Stream (Listening on /runs/EXP-8941/stream)
            </span>
          </div>

          <div className="space-y-2 font-mono text-xs">
            {TIMELINE_LOGS.map((log, idx) => (
              <div
                key={idx}
                className="flex items-start gap-4 p-2 rounded hover:bg-slate-900/50 transition border-l-2 border-transparent hover:border-indigo-500"
              >
                <span className="text-slate-500 shrink-0">{log.time}</span>
                <span className="font-semibold text-indigo-300 w-28 shrink-0">
                  [{log.agent}]
                </span>
                <span className="text-slate-300 flex-1">{log.msg}</span>
                <Badge
                  variant={log.status === "completed" ? "verified" : "running"}
                  className="text-[10px]"
                >
                  {log.status.toUpperCase()}
                </Badge>
              </div>
            ))}
          </div>
        </div>

        {/* Contextual Slide-Over Drawer */}
        <AgentDetailDrawer
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
        />
      </div>
    </AppShell>
  );
}
