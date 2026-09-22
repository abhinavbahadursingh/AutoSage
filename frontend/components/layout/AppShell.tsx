"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  PlusCircle,
  FlaskConical,
  Bot,
  Workflow,
  Database,
  ShieldCheck,
  GitFork,
  BrainCircuit,
  BarChart3,
  LineChart,
  Settings,
  ChevronLeft,
  ChevronRight,
  Activity,
  Cpu,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import { StatusIndicator } from "@/components/ui/StatusIndicator";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    title: "CORE",
    items: [
      { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
      { label: "New Experiment", href: "/experiments/new", icon: PlusCircle },
      { label: "Experiments", href: "/experiments", icon: FlaskConical },
    ],
  },
  {
    title: "PIPELINE",
    items: [
      { label: "Agents", href: "/agents", icon: Bot },
      { label: "Pipelines", href: "/pipelines", icon: Workflow },
      { label: "Datasets", href: "/datasets", icon: Database },
    ],
  },
  {
    title: "TRUST",
    items: [
      { label: "Verification", href: "/verification", icon: ShieldCheck },
      { label: "Evidence", href: "/evidence", icon: GitFork },
      { label: "Memory", href: "/memory", icon: BrainCircuit },
    ],
  },
  {
    title: "INSIGHTS",
    items: [
      { label: "Results", href: "/results", icon: BarChart3 },
      { label: "Evaluation", href: "/evaluation", icon: LineChart },
    ],
  },
  {
    title: "SYSTEM",
    items: [{ label: "Settings", href: "/settings", icon: Settings }],
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 font-sans text-slate-100">
      {/* Collapsible Sidebar */}
      <aside
        className={cn(
          "relative flex flex-col border-r border-slate-800/80 bg-slate-950 transition-all duration-300 ease-in-out z-30",
          collapsed ? "w-16" : "w-64"
        )}
      >
        {/* Sidebar Header */}
        <div className="flex h-16 items-center justify-between px-4 border-b border-slate-900">
          <Link href="/" className="flex items-center gap-3 overflow-hidden">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-600 font-bold text-white shadow-md shadow-indigo-500/20">
              AS
            </div>
            {!collapsed && (
              <div className="flex flex-col overflow-hidden">
                <span className="font-semibold tracking-tight text-slate-100 text-base">
                  AutoSage
                </span>
                <span className="text-[10px] font-mono uppercase tracking-widest text-indigo-400">
                  Verified AutoML
                </span>
              </div>
            )}
          </Link>

          <button
            onClick={() => setCollapsed(!collapsed)}
            className="rounded p-1 text-slate-400 hover:bg-slate-900 hover:text-slate-100"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>

        {/* Navigation Items */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
          {NAV_GROUPS.map((group) => (
            <div key={group.title} className="space-y-1">
              {!collapsed && (
                <p className="px-3 text-[10px] font-mono font-medium uppercase tracking-wider text-slate-500">
                  {group.title}
                </p>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const isActive =
                    pathname === item.href ||
                    (item.href !== "/dashboard" && pathname.startsWith(item.href));

                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      title={collapsed ? item.label : undefined}
                      className={cn(
                        "group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                        isActive
                          ? "bg-indigo-600/15 text-indigo-300 border-l-2 border-indigo-500"
                          : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
                      )}
                    >
                      <Icon
                        size={18}
                        className={cn(
                          "shrink-0 transition-colors",
                          isActive ? "text-indigo-400" : "text-slate-400 group-hover:text-slate-200"
                        )}
                      />
                      {!collapsed && (
                        <span className="truncate">{item.label}</span>
                      )}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* System Health / Status Footer */}
        {!collapsed && (
          <div className="p-4 border-t border-slate-900/80 bg-slate-950/40">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-slate-400 flex items-center gap-1.5">
                <Cpu size={13} className="text-indigo-400" /> Docker Sandbox
              </span>
              <StatusIndicator status="verified" label="Active" />
            </div>
            <p className="text-[11px] text-slate-500 mt-1">pgvector: 1,536-dim HNSW</p>
          </div>
        )}
      </aside>

      {/* Main Workspace */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Workspace Header Strip */}
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-800/80 bg-slate-950/80 px-6 backdrop-blur-md z-20">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
              <span>AutoSage</span>
              <span>/</span>
              <span className="text-slate-200 font-medium">Research Workspace</span>
            </div>
            <div className="h-4 w-[1px] bg-slate-800" />
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-slate-400">Active Run:</span>
              <Badge variant="running" className="animate-pulse-subtle">
                EXP-8941 • Churn Prediction
              </Badge>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 rounded border border-slate-800 bg-slate-900/90 px-2.5 py-1 text-xs font-mono text-slate-400">
              <Activity size={13} className="text-emerald-400" />
              <span>Verification Gate: Online</span>
            </div>
            <Link
              href="/experiments/new"
              className="flex items-center gap-2 rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 transition shadow-sm"
            >
              <PlusCircle size={14} />
              <span>New Experiment</span>
            </Link>
          </div>
        </header>

        {/* Scrollable Main Area */}
        <main className="flex-1 overflow-y-auto bg-slate-950">
          {children}
        </main>
      </div>
    </div>
  );
}
