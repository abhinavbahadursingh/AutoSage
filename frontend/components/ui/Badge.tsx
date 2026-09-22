import React from "react";
import { cn } from "@/lib/utils";

export type BadgeVariant =
  | "default"
  | "verified"
  | "running"
  | "processing"
  | "warning"
  | "error"
  | "pending";

interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: BadgeVariant;
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variantStyles: Record<BadgeVariant, string> = {
    default: "bg-indigo-950/60 text-indigo-300 border-indigo-500/30",
    verified: "bg-emerald-950/60 text-emerald-300 border-emerald-500/40",
    running: "bg-blue-950/60 text-blue-300 border-blue-500/40",
    processing: "bg-violet-950/60 text-violet-300 border-violet-500/40",
    warning: "bg-amber-950/60 text-amber-300 border-amber-500/40",
    error: "bg-rose-950/60 text-rose-300 border-rose-500/40",
    pending: "bg-slate-900/60 text-slate-400 border-slate-700/50",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors font-mono",
        variantStyles[variant],
        className
      )}
      {...props}
    />
  );
}
