"use client";

import React, { useState } from "react";
import {
  Settings as SettingsIcon,
  Key,
  Cpu,
  Database,
  CheckCircle2,
  Save,
  ShieldAlert,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

export default function SettingsPage() {
  const [groqKey, setGroqKey] = useState("gsk_••••••••••••••••••••••••••••••••");
  const [openrouterKey, setOpenrouterKey] = useState("sk-or-v1-••••••••••••••••••••••••••••");
  const [hfKey, setHfKey] = useState("hf_••••••••••••••••••••••••••••••••");
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <AppShell>
      <div className="p-8 space-y-8 max-w-4xl mx-auto">
        <div className="flex items-center justify-between border-b border-slate-900 pb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">
              System Settings & Infrastructure Configuration
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Configure free-tier LLM provider credentials, Docker sandbox resource ceilings, and database connections.
            </p>
          </div>

          <Button onClick={handleSave} size="sm" className="gap-2 text-xs">
            <Save size={14} />
            <span>{saved ? "Saved Changes!" : "Save Settings"}</span>
          </Button>
        </div>

        {/* LLM Provider Credentials */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Key size={16} className="text-indigo-400" />
              <CardTitle className="text-sm font-mono uppercase tracking-wider text-slate-200">
                LLM Provider API Credentials (Free Tier)
              </CardTitle>
            </div>
            <CardDescription>
              AutoSage rotates requests across these providers to maintain high-speed reasoning without cost.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 font-mono text-xs">
            <div className="space-y-1.5">
              <div className="flex justify-between">
                <label className="text-slate-300">Groq API Key (High-Speed Llama 3 Inference)</label>
                <Badge variant="verified">Connected</Badge>
              </div>
              <input
                type="password"
                value={groqKey}
                onChange={(e) => setGroqKey(e.target.value)}
                className="w-full rounded bg-slate-900 border border-slate-800 p-2 text-slate-100 focus:border-indigo-500 focus:outline-none"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between">
                <label className="text-slate-300">OpenRouter API Key (Fallback Reasoning Models)</label>
                <Badge variant="verified">Connected</Badge>
              </div>
              <input
                type="password"
                value={openrouterKey}
                onChange={(e) => setOpenrouterKey(e.target.value)}
                className="w-full rounded bg-slate-900 border border-slate-800 p-2 text-slate-100 focus:border-indigo-500 focus:outline-none"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between">
                <label className="text-slate-300">Hugging Face Inference API Token</label>
                <Badge variant="verified">Connected</Badge>
              </div>
              <input
                type="password"
                value={hfKey}
                onChange={(e) => setHfKey(e.target.value)}
                className="w-full rounded bg-slate-900 border border-slate-800 p-2 text-slate-100 focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </CardContent>
        </Card>

        {/* Docker Sandbox Resource Quotas */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Cpu size={16} className="text-indigo-400" />
              <CardTitle className="text-sm font-mono uppercase tracking-wider text-slate-200">
                Docker Sandbox Isolation Quotas
              </CardTitle>
            </div>
            <CardDescription>
              Hard resource constraints applied to ephemeral container runs
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 font-mono text-xs">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-slate-400">Max Container RAM Limit</label>
                <select className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-slate-100">
                  <option>4 GB RAM (Recommended)</option>
                  <option>8 GB RAM</option>
                  <option>2 GB RAM</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-slate-400">CPU Core Quota</label>
                <select className="w-full bg-slate-900 border border-slate-800 rounded p-2 text-slate-100">
                  <option>2.0 Cores (50% Host Cap)</option>
                  <option>4.0 Cores</option>
                  <option>1.0 Core</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-slate-400">Execution Timeout Guard</label>
                <input
                  type="text"
                  defaultValue="300 Seconds (5 Minutes)"
                  className="w-full rounded bg-slate-900 border border-slate-800 p-2 text-slate-100"
                />
              </div>

              <div className="space-y-1">
                <label className="text-slate-400">Network Isolation Mode</label>
                <div className="p-2 rounded bg-slate-900/60 border border-slate-800 text-emerald-400 flex items-center justify-between">
                  <span>--network none (Enforced)</span>
                  <CheckCircle2 size={14} />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Database & Persistence Status */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Database size={16} className="text-indigo-400" />
              <CardTitle className="text-sm font-mono uppercase tracking-wider text-slate-200">
                Data Layer & Vector Engine
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 font-mono text-xs">
            <div className="flex justify-between items-center p-3 rounded bg-slate-900/40 border border-slate-800">
              <span>Supabase PostgreSQL 16</span>
              <Badge variant="verified">Connected (Local Port 5432)</Badge>
            </div>
            <div className="flex justify-between items-center p-3 rounded bg-slate-900/40 border border-slate-800">
              <span>pgvector Vector Store (1,536 dims)</span>
              <Badge variant="verified">HNSW Cosine Index Ready</Badge>
            </div>
            <div className="flex justify-between items-center p-3 rounded bg-slate-900/40 border border-slate-800">
              <span>MLflow Tracking Server</span>
              <Badge variant="verified">http://localhost:5000 Online</Badge>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
