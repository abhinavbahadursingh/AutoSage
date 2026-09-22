"use client";

import React, { useState } from "react";
import {
  Database,
  UploadCloud,
  FileSpreadsheet,
  Layers,
  Search,
  CheckCircle2,
  AlertCircle,
  BarChart2,
  FileText,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface ColumnMeta {
  name: string;
  type: string;
  missingCount: number;
  missingPct: string;
  uniqueValues: number;
  statSample: string;
}

const SAMPLE_COLUMNS: ColumnMeta[] = [
  { name: "customer_id", type: "string", missingCount: 0, missingPct: "0.0%", uniqueValues: 102400, statSample: "Unique IDs (Excluded)" },
  { name: "tenure_months", type: "int64", missingCount: 0, missingPct: "0.0%", uniqueValues: 72, statSample: "Min: 1, Max: 72, Mean: 32.4" },
  { name: "monthly_charges", type: "float64", missingCount: 18636, missingPct: "18.2%", uniqueValues: 1580, statSample: "Median: 64.2, Mean: 68.1" },
  { name: "total_charges", type: "float64", missingCount: 204, missingPct: "0.2%", uniqueValues: 8940, statSample: "Skew: +2.84, Min: 18.8" },
  { name: "contract_type", type: "category", missingCount: 0, missingPct: "0.0%", uniqueValues: 3, statSample: "Month-to-month (55%), 1Yr (25%)" },
  { name: "churned_status (TARGET)", type: "int64", missingCount: 0, missingPct: "0.0%", uniqueValues: 2, statSample: "0: 90,112 (88%) | 1: 12,288 (12%)" },
];

export default function DatasetsPage() {
  const [selectedDataset, setSelectedDataset] = useState("customer_churn.parquet");

  return (
    <AppShell>
      <div className="p-8 space-y-8 max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-900 pb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">
              Dataset Experience & Explorer
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Upload, preview schemas, and inspect data health statistics before automated pipeline execution.
            </p>
          </div>

          <Button size="sm" className="gap-2 text-xs">
            <UploadCloud size={15} />
            <span>Upload New Dataset</span>
          </Button>
        </div>

        {/* Drag and Drop Zone */}
        <div className="rounded-xl border border-dashed border-slate-800 bg-slate-950/60 p-8 text-center hover:border-indigo-500/60 transition cursor-pointer">
          <div className="flex flex-col items-center gap-3 max-w-md mx-auto">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-950/60 text-indigo-400 border border-indigo-500/30">
              <UploadCloud size={24} />
            </div>
            <div>
              <span className="font-semibold text-sm text-slate-200 block">
                Drag and drop dataset files here
              </span>
              <p className="text-xs text-slate-500 mt-0.5">
                Supported formats: CSV, Parquet, TSV (Max file size: 250MB)
              </p>
            </div>
          </div>
        </div>

        {/* Active Dataset Overview */}
        <Card className="border-indigo-500/30 shadow-lg">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Badge variant="verified">PROFILE READY</Badge>
                <span className="text-xs font-mono text-slate-400">Parquet Format</span>
              </div>
              <CardTitle className="text-base font-semibold text-slate-100">
                {selectedDataset}
              </CardTitle>
            </div>
            <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
              <div>Rows: <span className="text-slate-100 font-semibold">102,400</span></div>
              <div>Columns: <span className="text-slate-100 font-semibold">21</span></div>
              <div>Size: <span className="text-slate-100 font-semibold">14.2 MB</span></div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Quick Profile Highlights */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
              <div className="p-3.5 rounded-lg border border-slate-800 bg-slate-900/40">
                <span className="text-slate-500 text-[10px] uppercase block">Target Variable</span>
                <span className="text-emerald-400 font-semibold text-sm">churned_status</span>
                <span className="text-[11px] text-slate-400 block mt-0.5">Binary (12% Positive Imbalance)</span>
              </div>

              <div className="p-3.5 rounded-lg border border-slate-800 bg-slate-900/40">
                <span className="text-slate-500 text-[10px] uppercase block">Missing Cells</span>
                <span className="text-amber-400 font-semibold text-sm">18,840 Total</span>
                <span className="text-[11px] text-slate-400 block mt-0.5">18.2% in 'monthly_charges'</span>
              </div>

              <div className="p-3.5 rounded-lg border border-slate-800 bg-slate-900/40">
                <span className="text-slate-500 text-[10px] uppercase block">High Cardinality Flag</span>
                <span className="text-indigo-400 font-semibold text-sm">1 Column</span>
                <span className="text-[11px] text-slate-400 block mt-0.5">'customer_id' (Auto-Excluded)</span>
              </div>
            </div>

            {/* Column Explorer Table */}
            <div className="space-y-2">
              <span className="text-xs font-mono uppercase tracking-wider text-slate-400">
                Column Attributes & Descriptive Statistics
              </span>

              <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="border-b border-slate-800 bg-slate-900/60 uppercase text-slate-400">
                    <tr>
                      <th className="p-3">Column Name</th>
                      <th className="p-3">Type</th>
                      <th className="p-3">Missing</th>
                      <th className="p-3">Distinct</th>
                      <th className="p-3">Statistical Summary</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-900">
                    {SAMPLE_COLUMNS.map((col) => (
                      <tr key={col.name} className="hover:bg-slate-900/40 transition">
                        <td className="p-3 font-semibold text-slate-200">
                          {col.name}
                        </td>
                        <td className="p-3 text-indigo-400">{col.type}</td>
                        <td className="p-3">
                          <span
                            className={
                              col.missingCount > 0
                                ? "text-amber-400 font-bold"
                                : "text-slate-400"
                            }
                          >
                            {col.missingPct} ({col.missingCount})
                          </span>
                        </td>
                        <td className="p-3 text-slate-300">{col.uniqueValues.toLocaleString()}</td>
                        <td className="p-3 text-slate-400 font-sans text-[11px]">
                          {col.statSample}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
