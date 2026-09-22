"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  ShieldCheck,
  Cpu,
  BrainCircuit,
  Terminal,
  FileCheck2,
  Lock,
  GitFork,
  ArrowRight,
  ChevronRight,
  Database,
  Layers,
  Sparkles,
  ExternalLink,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface PipelineStep {
  id: string;
  name: string;
  sub: string;
  description: string;
  codeSnippet: string;
  verifiedInvariant: string;
}

const PIPELINE_STEPS: PipelineStep[] = [
  {
    id: "task",
    name: "User Task",
    sub: "Natural Language",
    description:
      "Formulate your problem naturally. AutoSage automatically infers task type, target columns, optimization metrics, and evaluation splits.",
    codeSnippet: '# AutoSage Formulation\nTask: Binary Classification\nTarget: "churned"\nMetric: F1-Score (Macro)\nStratification: 5-Fold Cross Validation',
    verifiedInvariant: "Ensures intent is deterministically mapped before code generation.",
  },
  {
    id: "agents",
    name: "AI Agents",
    sub: "LangGraph Mesh",
    description:
      "Six specialized agents collaborate in an orchestrated state graph: Discovery, Profiling, Preprocessing, Model Selection, and Experimentation.",
    codeSnippet: '# LangGraph Multi-Agent Transition\nWorkflow.add_edge("profiler", "preprocessor")\nWorkflow.add_conditional_edges("verifier", evaluate_gate)',
    verifiedInvariant: "Strict separation of concerns; no single LLM hallucinates end-to-end.",
  },
  {
    id: "sandbox",
    name: "Experiment",
    sub: "Docker Isolation",
    description:
      "Trained estimators execute in ephemeral locked containers with non-root UID, zero host network access, and strict 4GB RAM ceilings.",
    codeSnippet: 'docker run --network none \\\n  --read-only \\\n  --memory=4g \\\n  --user=10001:10001 autosage-runner:latest',
    verifiedInvariant: "Hard execution timeout (300s) and AST-enforced zero system call policy.",
  },
  {
    id: "verification",
    name: "Verification",
    sub: "Rule & Metric Gate",
    description:
      "Automated verification intercepts target leakage, impossible metric ranges, overfitting anomalies, and trivial baseline failures.",
    codeSnippet: 'def verify_pipeline(metrics, ast_tree):\n    assert not has_target_leak(ast_tree)\n    assert metrics["val_f1"] > baseline["dummy_f1"]',
    verifiedInvariant: "Pipeline is rejected and returned for agent self-correction if any check fails.",
  },
  {
    id: "pipeline",
    name: "ML Pipeline",
    sub: "Verified Artifact",
    description:
      "Delivers a self-contained, reproducible Python bundle with pinned dependencies, model weights, and complete decision lineage.",
    codeSnippet: '# Standalone deployment\nimport joblib\npipeline = joblib.load("pipeline.joblib")\npredictions = pipeline.predict(new_data)',
    verifiedInvariant: "100% reproducible execution guaranteed across independent runtimes.",
  },
];

export default function LandingPage() {
  const [selectedStep, setSelectedStep] = useState<PipelineStep>(PIPELINE_STEPS[0]);

  return (
    <div className="min-h-screen bg-slate-950 font-sans text-slate-100 selection:bg-indigo-500 selection:text-white">
      {/* Top Navigation */}
      <header className="border-b border-slate-900 bg-slate-950/70 backdrop-blur-md sticky top-0 z-50">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 font-bold text-white shadow-md shadow-indigo-500/20">
              AS
            </div>
            <span className="font-semibold tracking-tight text-lg text-slate-100">
              AutoSage
            </span>
            <span className="rounded bg-indigo-950/80 px-2 py-0.5 text-[10px] font-mono font-medium text-indigo-400 border border-indigo-500/30">
              RESEARCH GRADE
            </span>
          </div>

          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-400">
            <a href="#how-it-works" className="hover:text-slate-100 transition">
              Workflow
            </a>
            <a href="#verification" className="hover:text-slate-100 transition">
              Verification Engine
            </a>
            <a href="#evidence" className="hover:text-slate-100 transition">
              Evidence Trail
            </a>
            <a href="#architecture" className="hover:text-slate-100 transition">
              Architecture
            </a>
          </nav>

          <div className="flex items-center gap-3">
            <Link
              href="/dashboard"
              className="rounded-md border border-slate-800 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-800 transition"
            >
              Research Console
            </Link>
            <Link
              href="/experiments/new"
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition shadow-sm"
            >
              Start Experiment
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-20 pb-24 border-b border-slate-900">
        <div className="mx-auto max-w-7xl px-6 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-950/40 px-3.5 py-1 text-xs font-mono text-indigo-300 mb-8">
            <Sparkles size={14} className="text-indigo-400" />
            <span>Autonomous ML with Empirical Verification & Reasoning Lineage</span>
          </div>

          <h1 className="mx-auto max-w-4xl text-5xl font-extrabold tracking-tight sm:text-6xl text-slate-100 leading-tight">
            From Natural Language to{" "}
            <span className="bg-gradient-to-r from-indigo-400 via-cyan-300 to-emerald-400 bg-clip-text text-transparent">
              Verified ML Pipelines
            </span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-400 leading-relaxed">
            AutoSage replaces unconstrained prompt-and-pray LLM code generation with a
            multi-agent research architecture: AST safety isolation, empirical Docker experimentation,
            and auditable mathematical verification.
          </p>

          <div className="mt-10 flex justify-center gap-4">
            <Link href="/experiments/new">
              <Button size="lg" className="gap-2">
                Start Experiment <ArrowRight size={16} />
              </Button>
            </Link>
            <Link href="/dashboard">
              <Button variant="outline" size="lg" className="gap-2">
                Explore Dashboard
              </Button>
            </Link>
          </div>

          {/* Interactive Hero Pipeline Explorer */}
          <div className="mt-16 rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm text-left max-w-5xl mx-auto shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
              <div className="flex items-center gap-2">
                <Layers size={16} className="text-indigo-400" />
                <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-300">
                  Interactive End-to-End Pipeline Visualization
                </span>
              </div>
              <span className="text-xs font-mono text-slate-500">
                Click any stage to inspect safety contracts
              </span>
            </div>

            {/* Pipeline Stage Nodes */}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
              {PIPELINE_STEPS.map((step, idx) => {
                const isSelected = selectedStep.id === step.id;
                return (
                  <button
                    key={step.id}
                    onClick={() => setSelectedStep(step)}
                    className={`flex flex-col p-3 rounded-lg border text-left transition-all cursor-pointer ${
                      isSelected
                        ? "bg-indigo-950/70 border-indigo-500 shadow-md shadow-indigo-500/10 ring-1 ring-indigo-500/50"
                        : "bg-slate-950/80 border-slate-800 hover:border-slate-700 text-slate-400"
                    }`}
                  >
                    <div className="flex items-center justify-between w-full mb-1">
                      <span className="text-[10px] font-mono text-slate-500">
                        0{idx + 1}
                      </span>
                      {isSelected && (
                        <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-ping" />
                      )}
                    </div>
                    <span className="font-semibold text-sm text-slate-200">
                      {step.name}
                    </span>
                    <span className="text-xs font-mono text-slate-500">
                      {step.sub}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Stage Detail Drawer */}
            <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6 p-4 rounded-lg bg-slate-950 border border-slate-800/80">
              <div className="space-y-3">
                <div className="inline-flex items-center gap-2">
                  <span className="font-semibold text-base text-slate-100">
                    {selectedStep.name}
                  </span>
                  <Badge variant="verified">Stage Invariant Verified</Badge>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  {selectedStep.description}
                </p>
                <div className="rounded border border-emerald-500/20 bg-emerald-950/30 p-2.5 text-xs text-emerald-300 font-mono">
                  <span className="font-semibold block mb-1">Safety Invariant:</span>
                  {selectedStep.verifiedInvariant}
                </div>
              </div>

              <div className="rounded bg-slate-900/90 border border-slate-800 p-3 font-mono text-xs text-indigo-300 overflow-x-auto">
                <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2 border-b border-slate-800 pb-1">
                  Generated Runtime Representation
                </div>
                <pre>{selectedStep.codeSnippet}</pre>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Core Research Capabilities */}
      <section id="verification" className="py-20 border-b border-slate-900 bg-slate-950/40">
        <div className="mx-auto max-w-7xl px-6">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl font-bold tracking-tight text-slate-100 sm:text-4xl">
              Why Verification Matters in AutoML
            </h2>
            <p className="mt-4 text-slate-400 text-sm leading-relaxed">
              Standard LLM code generators frequently introduce critical statistical bugs: fitting scalers before train/test splitting, leaking target signals, or optimizing meaningless default metrics. AutoSage prevents this by design.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-6 space-y-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-950/60 text-emerald-400 border border-emerald-500/30">
                <ShieldCheck size={20} />
              </div>
              <h3 className="text-lg font-semibold text-slate-100">
                AST Data Leakage Detector
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Python Abstract Syntax Tree (AST) analysis inspects generated code prior to container dispatch, verifying strict split isolation and forbidding unauthorized system calls.
              </p>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-6 space-y-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-950/60 text-indigo-400 border border-indigo-500/30">
                <Cpu size={20} />
              </div>
              <h3 className="text-lg font-semibold text-slate-100">
                Hardened Docker Sandbox
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Model exploration happens in an isolated Docker runtime with non-root UID 10001, `--network none`, read-only root filesystems, and strict CPU/RAM ceilings.
              </p>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-6 space-y-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-950/60 text-violet-400 border border-violet-500/30">
                <BrainCircuit size={20} />
              </div>
              <h3 className="text-lg font-semibold text-slate-100">
                pgvector Memory Reuse
              </h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Empirically verified winning strategies are fingerprinted and indexed in PostgreSQL pgvector, providing few-shot transfer learning for future tabular tasks.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <footer className="border-t border-slate-900 bg-slate-950 py-12 text-center text-xs text-slate-500">
        <div className="mx-auto max-w-7xl px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-300">AutoSage</span>
            <span>— A Verified Multi-Agent System for Automated Machine Learning</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/dashboard" className="hover:text-slate-300">Dashboard</Link>
            <Link href="/experiments" className="hover:text-slate-300">Experiments</Link>
            <Link href="/verification" className="hover:text-slate-300">Verification</Link>
            <Link href="/settings" className="hover:text-slate-300">Settings</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
