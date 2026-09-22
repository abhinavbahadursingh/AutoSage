"use client";

import React from "react";
import {
  FileSearch,
  BarChart2,
  Cpu,
  Brain,
  FlaskConical,
  ShieldCheck,
  CheckCircle2,
  Clock,
  AlertCircle,
  Sparkles,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { StatusIndicator } from "@/components/ui/StatusIndicator";

export interface AgentNodeData {
  id: string;
  name: string;
  role: string;
  status: "completed" | "running" | "pending" | "failed";
  runtime: string;
  confidence?: string;
  decision?: string;
  evidenceCount: number;
  outputSnippet?: string;
  rationale?: string;
  icon: React.ElementType;
}

interface WorkflowGraphProps {
  nodes: AgentNodeData[];
  selectedNodeId: string;
  onSelectNode: (node: AgentNodeData) => void;
}

export function WorkflowGraph({
  nodes,
  selectedNodeId,
  onSelectNode,
}: WorkflowGraphProps) {
  return (
    <div className="relative w-full rounded-xl border border-slate-800 bg-slate-950/80 p-8 graph-grid overflow-x-auto shadow-inner">
      <div className="min-w-[800px] flex items-center justify-between gap-4 relative py-6">
        {nodes.map((node, index) => {
          const Icon = node.icon;
          const isSelected = selectedNodeId === node.id;
          const isRunning = node.status === "running";
          const isCompleted = node.status === "completed";

          return (
            <React.Fragment key={node.id}>
              {/* Agent Node */}
              <div
                onClick={() => onSelectNode(node)}
                className={`relative flex flex-col items-center p-4 rounded-xl border transition-all cursor-pointer w-44 z-10 select-none ${
                  isSelected
                    ? "bg-slate-900 border-indigo-500 shadow-lg shadow-indigo-500/20 ring-2 ring-indigo-500/50"
                    : isRunning
                    ? "bg-indigo-950/40 border-indigo-500/80 shadow-md shadow-indigo-500/10 ring-1 ring-indigo-500 animate-pulse-subtle"
                    : isCompleted
                    ? "bg-slate-950/90 border-emerald-500/40 hover:border-emerald-500/80"
                    : "bg-slate-950/40 border-slate-800/80 opacity-60 hover:opacity-100"
                }`}
              >
                {/* Node Status Indicator Pill */}
                <div className="flex items-center justify-between w-full mb-3 text-[10px] font-mono">
                  <span className="text-slate-500">0{index + 1}</span>
                  <StatusIndicator
                    status={node.status === "completed" ? "verified" : node.status}
                    label={node.status.toUpperCase()}
                  />
                </div>

                {/* Node Icon */}
                <div
                  className={`flex h-12 w-12 items-center justify-center rounded-lg mb-2 transition-colors ${
                    isCompleted
                      ? "bg-emerald-950/60 text-emerald-400 border border-emerald-500/40"
                      : isRunning
                      ? "bg-indigo-950/80 text-indigo-300 border border-indigo-500 animate-pulse"
                      : "bg-slate-900 text-slate-400 border border-slate-800"
                  }`}
                >
                  <Icon size={22} />
                </div>

                {/* Node Labels */}
                <span className="font-semibold text-xs text-slate-100 text-center line-clamp-1">
                  {node.name}
                </span>
                <span className="text-[11px] text-slate-400 text-center font-mono mt-0.5">
                  {node.role}
                </span>

                {/* Runtime Badge */}
                <div className="mt-3 pt-2 border-t border-slate-800/80 w-full flex items-center justify-between text-[10px] font-mono text-slate-500">
                  <span>Runtime:</span>
                  <span className="text-slate-300 font-semibold">{node.runtime}</span>
                </div>
              </div>

              {/* Edge Connecting Arrow */}
              {index < nodes.length - 1 && (
                <div className="flex-1 flex items-center justify-center relative px-2">
                  <div
                    className={`h-0.5 w-full transition-all ${
                      isCompleted
                        ? "bg-emerald-500/50"
                        : isRunning
                        ? "bg-indigo-500/50 animate-pulse"
                        : "bg-slate-800"
                    }`}
                  />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      <div className="text-right text-[11px] font-mono text-slate-500 mt-2">
        * Click any agent to inspect decisions, empirical evidence, and raw code outputs in the side drawer.
      </div>
    </div>
  );
}
