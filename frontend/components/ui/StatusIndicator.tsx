import React from "react";
import { cn } from "@/lib/utils";

export type IndicatorStatus =
  | "verified"
  | "completed"
  | "running"
  | "processing"
  | "warning"
  | "error"
  | "failed"
  | "pending";

interface StatusIndicatorProps {
  status: IndicatorStatus;
  label?: string;
  className?: string;
}

export function StatusIndicator({ status, label, className }: StatusIndicatorProps) {
  const isVerified = status === "verified" || status === "completed";
  const isFailed = status === "error" || status === "failed";

  const dotStyles: Record<string, string> = {
    verified: "bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.8)]",
    completed: "bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.8)]",
    running: "bg-blue-400 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.8)]",
    processing: "bg-violet-400 animate-pulse shadow-[0_0_8px_rgba(139,92,246,0.8)]",
    warning: "bg-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.8)]",
    error: "bg-rose-400 shadow-[0_0_8px_rgba(244,63,94,0.8)]",
    failed: "bg-rose-400 shadow-[0_0_8px_rgba(244,63,94,0.8)]",
    pending: "bg-slate-600",
  };

  const textStyles: Record<string, string> = {
    verified: "text-emerald-400",
    completed: "text-emerald-400",
    running: "text-blue-400",
    processing: "text-violet-400",
    warning: "text-amber-400",
    error: "text-rose-400",
    failed: "text-rose-400",
    pending: "text-slate-500",
  };

  return (
    <div className={cn("inline-flex items-center gap-2 text-xs font-mono font-medium", className)}>
      <span className={cn("h-2 w-2 rounded-full", dotStyles[status] || "bg-slate-600")} />
      {label && <span className={textStyles[status] || "text-slate-400"}>{label}</span>}
    </div>
  );
}
