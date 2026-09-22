"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  Edit3,
  ArrowRight,
  ShieldAlert,
  Brain,
  Sliders,
} from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

interface ParsedInterpretation {
  taskType: string;
  targetColumn: string;
  evaluationMetric: string;
  datasetName: string;
  splitStrategy: string;
  imbalanceHandling: string;
}

export default function NewExperimentPage() {
  const router = useRouter();

  // Natural language state
  const [prompt, setPrompt] = useState(
    "Train a model to classify customer churn using customer_churn.parquet. The dataset has ~12% churn rate (severe imbalance). Prioritize recall and F1 score over raw accuracy, and make sure to prevent target leakage."
  );
  const [datasetFile, setDatasetFile] = useState<string>("customer_churn.parquet");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  // Interpretation state (parsed by AutoSage Pipeline Preparation Agent)
  const [interpretation, setInterpretation] = useState<ParsedInterpretation>({
    taskType: "Binary Classification",
    targetColumn: "churned_status",
    evaluationMetric: "F1 Score (Macro)",
    datasetName: "customer_churn.parquet",
    splitStrategy: "Stratified 5-Fold Cross-Validation",
    imbalanceHandling: "Class-Weighted Loss & Target Encoding",
  });

  const handleFormulate = () => {
    setIsSubmitting(true);
    setTimeout(() => {
      setIsSubmitting(false);
      setShowConfirmation(true);
    }, 600);
  };

  const handleExecute = () => {
    // Navigate to live agent workflow screen
    router.push("/experiments/EXP-8941/workflow");
  };

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto p-8 space-y-8">
        <div>
          <div className="inline-flex items-center gap-2 text-xs font-mono text-indigo-400 mb-1">
            <Sparkles size={14} />
            <span>NATURAL-LANGUAGE-DRIVEN FORMULATION</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-100">
            What do you want to build?
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Express your machine learning objective in plain English. AutoSage will interpret the task, discover the dataset schema, and construct a verified LangGraph workflow.
          </p>
        </div>

        {/* Primary Natural Language Prompt Box */}
        <Card className="border-indigo-500/30 shadow-lg">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-mono uppercase tracking-wider text-slate-300">
              ML Problem Specification
            </CardTitle>
            <CardDescription>
              Specify your domain requirements, metric preferences, and latency constraints
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <textarea
              rows={4}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe your ML problem naturally (e.g. 'Predict customer churn from customer_data.csv, focus on F1-score due to imbalance...')"
              className="w-full rounded-md border border-slate-800 bg-slate-900/90 p-4 text-sm text-slate-100 placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-sans leading-relaxed"
            />

            {/* Secondary Controls: Dataset Upload & Task Detection */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <div className="rounded-lg border border-dashed border-slate-800 bg-slate-900/40 p-4 text-center hover:border-slate-700 transition">
                <div className="flex flex-col items-center gap-2">
                  <FileSpreadsheet className="text-indigo-400" size={24} />
                  <div className="text-xs">
                    <span className="font-semibold text-slate-200">
                      {datasetFile}
                    </span>
                    <span className="text-slate-500 block">14.2 MB &bull; 102,400 rows &bull; 21 cols</span>
                  </div>
                  <Button variant="outline" size="sm" className="mt-1 text-xs">
                    Replace Dataset
                  </Button>
                </div>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono uppercase text-slate-400">
                      Task Auto-Detection
                    </span>
                    <Badge variant="verified">Auto Detect: ON</Badge>
                  </div>
                  <p className="text-xs text-slate-300 mt-2">
                    AutoSage analyzes the label distribution and column semantics to infer task type, target, and split.
                  </p>
                </div>
                <div className="text-[11px] font-mono text-slate-500 pt-2 border-t border-slate-900">
                  Memory Match: Enabled (Querying past verified runs)
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-4">
              <Button
                onClick={handleFormulate}
                disabled={isSubmitting || !prompt.trim()}
                size="lg"
                className="gap-2"
              >
                {isSubmitting ? (
                  <span>Interpreting Intent...</span>
                ) : (
                  <>
                    <span>Start Experiment</span>
                    <ArrowRight size={16} />
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* AutoSage Interpretation Confirmation Gate */}
        {showConfirmation && (
          <div className="rounded-xl border border-emerald-500/40 bg-slate-950 p-6 shadow-2xl space-y-6 animate-in fade-in duration-300">
            <div className="flex items-center justify-between border-b border-slate-900 pb-4">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-500/40">
                  <CheckCircle2 size={18} />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-slate-100">
                    AutoSage Formulation Verified
                  </h2>
                  <p className="text-xs text-slate-400">
                    Review and confirm AutoSage's formal translation before container dispatch.
                  </p>
                </div>
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsEditing(!isEditing)}
                className="gap-1.5 text-xs"
              >
                <Edit3 size={13} />
                <span>{isEditing ? "Save Adjustments" : "Edit Specification"}</span>
              </Button>
            </div>

            {/* Parsed Attributes Table */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
              <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 space-y-1">
                <span className="text-slate-500 block uppercase">Inferred Task Type</span>
                {isEditing ? (
                  <select
                    value={interpretation.taskType}
                    onChange={(e) =>
                      setInterpretation({ ...interpretation, taskType: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded p-1.5 text-slate-100"
                  >
                    <option>Binary Classification</option>
                    <option>Multiclass Classification</option>
                    <option>Regression</option>
                  </select>
                ) : (
                  <span className="text-indigo-300 font-semibold text-sm">
                    {interpretation.taskType}
                  </span>
                )}
              </div>

              <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 space-y-1">
                <span className="text-slate-500 block uppercase">Target Variable</span>
                {isEditing ? (
                  <input
                    type="text"
                    value={interpretation.targetColumn}
                    onChange={(e) =>
                      setInterpretation({ ...interpretation, targetColumn: e.target.value })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded p-1.5 text-slate-100"
                  />
                ) : (
                  <span className="text-emerald-400 font-semibold text-sm">
                    {interpretation.targetColumn}
                  </span>
                )}
              </div>

              <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 space-y-1">
                <span className="text-slate-500 block uppercase">Optimization Metric</span>
                {isEditing ? (
                  <select
                    value={interpretation.evaluationMetric}
                    onChange={(e) =>
                      setInterpretation({
                        ...interpretation,
                        evaluationMetric: e.target.value,
                      })
                    }
                    className="w-full bg-slate-950 border border-slate-700 rounded p-1.5 text-slate-100"
                  >
                    <option>F1 Score (Macro)</option>
                    <option>ROC-AUC</option>
                    <option>Balanced Accuracy</option>
                    <option>Log Loss</option>
                  </select>
                ) : (
                  <span className="text-slate-100 font-semibold text-sm">
                    {interpretation.evaluationMetric}
                  </span>
                )}
              </div>

              <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 space-y-1">
                <span className="text-slate-500 block uppercase">Partitioning Strategy</span>
                <span className="text-slate-300 font-semibold text-sm">
                  {interpretation.splitStrategy}
                </span>
              </div>
            </div>

            {/* Invariant Guarantee Alert */}
            <div className="flex items-start gap-3 rounded-lg border border-indigo-500/20 bg-indigo-950/30 p-3 text-xs text-indigo-300">
              <Brain size={18} className="shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold block">Execution Safety Agreement:</span>
                Target leakage check, AST code inspection, and a locked Docker runtime will be enforced before any pipeline artifact is accepted.
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="outline"
                size="md"
                onClick={() => setShowConfirmation(false)}
              >
                Back to Prompt
              </Button>
              <Button
                variant="verified"
                size="md"
                onClick={handleExecute}
                className="gap-2"
              >
                <span>Confirm & Execute (⌘↵)</span>
                <ArrowRight size={15} />
              </Button>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
