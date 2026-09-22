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
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { StatusIndicator } from "@/components/ui/StatusIndicator";

interface AgentCardData {
  id: string;
  name: string;
  role: string;
  purpose: string;
  status: "verified" | "running" | "pending";
  totalExecutions: number;
  successRate: string;
  evidenceCount: number;
  avgLatency: string;
  icon: React.ElementType;
}

const AGENTS_LIST: AgentCardData[] = [
  {
    id: "discovery",
    name: "Dataset Discovery Agent",
    role: "File Inspection & Ingestion",
    purpose: "Sniffs raw CSV and Parquet headers, verifies delimiter and UTF-8 encoding, and prevents corrupt file pipeline launches.",
    status: "verified",
    totalExecutions: 128,
    successRate: "100.0%",
    evidenceCount: 128,
    avgLatency: "1.2s",
    icon: FileSearch,
  },
  {
    id: "profiler",
    name: "Profiler Agent",
    role: "Statistical Profiling",
    purpose: "Generates descriptive statistics, flags severe skewness, detects high-cardinality features, and computes target imbalance ratios.",
    status: "verified",
    totalExecutions: 128,
    successRate: "96.8%",
    evidenceCount: 256,
    avgLatency: "5.8s",
    icon: BarChart2,
  },
  {
    id: "preprocessor",
    name: "Preprocessor Agent",
    role: "AST Code Synthesizer",
    purpose: "Synthesizes leak-free transformation pipelines using AST security rules, fitting exclusively on training subsets.",
    status: "verified",
    totalExecutions: 142,
    successRate: "91.5%",
    evidenceCount: 384,
    avgLatency: "8.4s",
    icon: Cpu,
  },
  {
    id: "model_selector",
    name: "Model Selector Agent",
    role: "Algorithm Hypothesizer",
    purpose: "Evaluates tabular data scale and latency constraints to select candidate algorithms (LightGBM, XGBoost, Random Forest).",
    status: "running",
    totalExecutions: 134,
    successRate: "94.0%",
    evidenceCount: 412,
    avgLatency: "7.2s",
    icon: Brain,
  },
  {
    id: "experimenter",
    name: "ML Experiment Agent",
    role: "Docker Sandbox Dispatcher",
    purpose: "Executes Python training scripts inside locked Docker containers with --network none and strict 4GB RAM resource ceilings.",
    status: "pending",
    totalExecutions: 150,
    successRate: "89.3%",
    evidenceCount: 150,
    avgLatency: "42.1s",
    icon: FlaskConical,
  },
  {
    id: "verifier",
    name: "Verification Engine",
    role: "Empirical Gatekeeper",
    purpose: "Audits AST code, verifies metric bounds, catches overfitting, and asserts dominance over trivial baseline models.",
    status: "pending",
    totalExecutions: 150,
    successRate: "98.0%",
    evidenceCount: 450,
    avgLatency: "1.8s",
    icon: ShieldCheck,
  },
];

export default function AgentsPage() {
  return (
    <AppShell>
      <div className="p-8 space-y-8 max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-900 pb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="verified">ORCHESTRATION MESH ONLINE</Badge>
              <span className="text-xs font-mono text-slate-400">LangGraph StateGraph Engine</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">
              Specialized Multi-Agent Mesh
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Discrete, specialized agents collaborate in an asynchronous directed graph to discover, transform, benchmark, and verify ML pipelines.
            </p>
          </div>

          <Link href="/workflow">
            <Button size="sm" className="gap-1.5 text-xs">
              <span>View Active Graph</span>
              <ChevronRight size={14} />
            </Button>
          </Link>
        </div>

        {/* 6 Core Agent Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {AGENTS_LIST.map((agent) => {
            const Icon = agent.icon;
            return (
              <Card
                key={agent.id}
                className="hover:border-slate-700 transition flex flex-col justify-between"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-950/80 text-indigo-400 border border-indigo-500/30">
                      <Icon size={20} />
                    </div>
                    <StatusIndicator
                      status={agent.status}
                      label={agent.status.toUpperCase()}
                    />
                  </div>
                  <CardTitle className="text-base font-semibold text-slate-100">
                    {agent.name}
                  </CardTitle>
                  <CardDescription className="font-mono text-xs text-indigo-300">
                    {agent.role}
                  </CardDescription>
                </CardHeader>

                <CardContent className="space-y-4">
                  <p className="text-xs text-slate-300 leading-relaxed font-sans">
                    {agent.purpose}
                  </p>

                  <div className="grid grid-cols-3 gap-2 pt-3 border-t border-slate-900 font-mono text-center text-xs">
                    <div className="p-2 rounded bg-slate-900/40 border border-slate-800/80">
                      <span className="text-[10px] text-slate-500 block">Runs</span>
                      <span className="text-slate-200 font-semibold">{agent.totalExecutions}</span>
                    </div>
                    <div className="p-2 rounded bg-slate-900/40 border border-slate-800/80">
                      <span className="text-[10px] text-slate-500 block">Success</span>
                      <span className="text-emerald-400 font-semibold">{agent.successRate}</span>
                    </div>
                    <div className="p-2 rounded bg-slate-900/40 border border-slate-800/80">
                      <span className="text-[10px] text-slate-500 block">Evidence</span>
                      <span className="text-indigo-300 font-semibold">{agent.evidenceCount}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </AppShell>
  );
}
