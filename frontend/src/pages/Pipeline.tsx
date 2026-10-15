import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Sparkles,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Bot,
  Zap,
  GitBranch,
  RotateCcw,
  Info,
} from 'lucide-react'
import { PageHeader } from '../components/layout/Sidebar'
import { Badge } from '../components/ui/Badge'
import { PlannedPipelineGraph } from '../components/graph/PlannedPipelineGraph'
import { PlanActions } from '../components/pipeline/PlanActions'
import { PlanAnalysisPanel } from '../components/pipeline/PlanAnalysisPanel'
import type { PipelinePlan, PipelineStage } from '../data/plannedGraph'
import { api, ApiError } from '../lib/api'
import {
  clearPipelinePlanDraft,
  getPipelinePlanDraft,
  setPipelinePlanDraft,
  subscribePipelinePlanDraft,
  type PipelinePlanDraft,
} from '../lib/pipelinePlanStore'

// ── Example prompts ──────────────────────────────────────────────────────────

const EXAMPLES = [
  'Predict customer churn using the uploaded dataset. Compare several models and optimize for recall.',
  'Estimate default probability on the Q3 lending file; probabilities must be well calibrated.',
  'Route support tickets to the right team. Allow multiple labels per ticket.',
  'Forecast delivery ETA in minutes and alert if feature drift exceeds PSI 0.2.',
  'Detect fraudulent transactions in real-time with explainability requirements.',
  'Segment customers based on purchasing behavior for targeted marketing campaigns.',
]

// ── Helpers ──────────────────────────────────────────────────────────────────

function complexityColor(c: string): string {
  if (c === 'low') return 'text-emerald-400'
  if (c === 'medium') return 'text-amber-400'
  return 'text-rose-400'
}

function complexityBg(c: string): string {
  if (c === 'low') return 'bg-emerald-400/10 border-emerald-400/30'
  if (c === 'medium') return 'bg-amber-400/10 border-amber-400/30'
  return 'bg-rose-400/10 border-rose-400/30'
}

// ── Stage Detail ─────────────────────────────────────────────────────────────

function StageDetail({ stage }: { stage: PipelineStage }) {
  return (
    <motion.div
      key={stage.id}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="rounded-xl border border-[var(--as-border)] bg-[var(--as-glass-bg)] p-4"
    >
      <div className="flex items-center gap-2 mb-2">
        <Bot size={14} className="text-violet-400" />
        <span className="text-[15px] font-semibold text-[var(--as-text)]">{stage.name}</span>
        {stage.optional && <Badge tone="dim">optional</Badge>}
      </div>
      <p className="text-[13.5px] text-[var(--as-text-2)] leading-relaxed mb-3">
        {stage.description}
      </p>

      <div className="grid grid-cols-2 gap-3 text-[12.5px]">
        <div>
          <span className="text-[var(--as-text-3)]">Agent</span>
          <span className="ml-2 text-[var(--as-text)]">{stage.agent}</span>
        </div>
        <div>
          <span className="text-[var(--as-text-3)]">Role</span>
          <span className="ml-2 text-[var(--as-text)]">{stage.role}</span>
        </div>
        <div>
          <span className="text-[var(--as-text-3)]">Est. duration</span>
          <span className="ml-2 text-[var(--as-text)]">{stage.estimated_duration}</span>
        </div>
        <div>
          <span className="text-[var(--as-text-3)]">Outputs</span>
          <span className="ml-2 text-[var(--as-text)]">{stage.outputs.join(', ') || '—'}</span>
        </div>
      </div>

      {stage.inputs.length > 0 && (
        <div className="mt-3 pt-2 border-t border-[var(--as-border)]">
          <span className="text-[11px] text-[var(--as-text-3)] uppercase tracking-wider">Inputs</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {stage.inputs.map((inp) => (
              <span
                key={inp}
                className="mono text-[11px] px-1.5 py-0.5 rounded bg-[var(--as-glass-bg-2)] border border-[var(--as-border)] text-[var(--as-text-2)]"
              >
                {inp}
              </span>
            ))}
          </div>
        </div>
      )}

      {stage.outputs.length > 0 && (
        <div className="mt-3 pt-2 border-t border-[var(--as-border)]">
          <span className="text-[11px] text-[var(--as-text-3)] uppercase tracking-wider">Outputs</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {stage.outputs.map((out) => (
              <span
                key={out}
                className="mono text-[11px] px-1.5 py-0.5 rounded bg-[var(--as-glass-bg-2)] border border-[var(--as-border)] text-[var(--as-text-2)]"
              >
                {out}
              </span>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  )
}

// ── Main Page ────────────────────────────────────────────────────────────────

export function PipelinePage() {
  const [description, setDescription] = useState('')
  // The planner endpoint accepts these three as planning context. Leaving them
  // empty sends the backend blank strings, exactly as before — they only sharpen
  // the plan when the user actually supplies them.
  const [datasetName, setDatasetName] = useState('')
  const [targetColumn, setTargetColumn] = useState('')
  const [taskType, setTaskType] = useState('')
  const [plan, setPlan] = useState<PipelinePlan | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedStage, setSelectedStage] = useState<string | null>(null)
  // Run id of the Generate & Verify session that handed this plan over, if any.
  const [originRunId, setOriginRunId] = useState<string | null>(null)
  const appliedDraftRef = useRef<string | null>(null)
  const [plannerStatus, setPlannerStatus] = useState<{
    available: boolean
    llm_available: boolean
    fallback_enabled: boolean
  } | null>(null)

  // Check planner status on mount
  useEffect(() => {
    api
      .pipelineStatus()
      .then(setPlannerStatus)
      .catch(() => setPlannerStatus(null))
  }, [])

  // Adopt the plan handed over by "Generate & Verify" (the Objectives page
  // plans the same problem in the background). Each draft is applied once —
  // a plan generated here by hand is not clobbered by an older draft.
  useEffect(() => {
    const adopt = (draft: PipelinePlanDraft | null) => {
      if (!draft || draft.id === appliedDraftRef.current) return
      appliedDraftRef.current = draft.id
      setDescription(draft.description)
      setPlan(draft.plan)
      setSelectedStage(draft.plan.stages[0]?.id ?? null)
      setOriginRunId(draft.runId)
      setError(null)
    }
    adopt(getPipelinePlanDraft())
    return subscribePipelinePlanDraft(adopt)
  }, [])

  const generatePlan = useCallback(async () => {
    if (!description.trim() || loading) return
    setLoading(true)
    setError(null)
    setPlan(null)
    setSelectedStage(null)
    setOriginRunId(null)
    try {
      const result = await api.generatePipelinePlan({
        description: description.trim(),
        ...(datasetName.trim() ? { dataset_name: datasetName.trim() } : {}),
        ...(targetColumn.trim() ? { target_column: targetColumn.trim() } : {}),
        ...(taskType ? { task_type: taskType } : {}),
      })
      setPlan(result)
      // Persist it: this page unmounts on navigation, so the stored draft is
      // what brings the plan back when the user returns. A new generation
      // (a new query) replaces the previous one.
      const draft = setPipelinePlanDraft({
        description: description.trim(),
        plan: result,
        runId: null,
      })
      appliedDraftRef.current = draft.id
      // Auto-select first stage
      if (result.stages.length > 0) {
        setSelectedStage(result.stages[0].id)
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to generate pipeline plan'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [description, datasetName, targetColumn, taskType, loading])

  const selectedStageData = useMemo(() => {
    if (!plan || !selectedStage) return null
    return plan.stages.find((s) => s.id === selectedStage) ?? null
  }, [plan, selectedStage])

  return (
    <div className="flex h-full min-w-0 flex-col">
      <PageHeader
        title="Pipeline Planner"
        subtitle="Describe an experiment and AutoSage designs a pipeline, then lays it out as a navigable flow graph."
        right={
          <div className="flex items-center gap-3">
            {plannerStatus && (
              <div className="flex items-center gap-2 text-[12px] text-[var(--as-text-3)]">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    plannerStatus.llm_available ? 'bg-emerald-400' : 'bg-amber-400'
                  }`}
                />
                {plannerStatus.llm_available ? 'LLM powered' : 'Heuristic mode'}
              </div>
            )}
          </div>
        }
      />

      <div className="flex-1 overflow-y-auto">
        <div className="w-full px-3 py-6">
          {/* ── Input Section ── */}
          <div className="rounded-xl border border-[var(--as-border)] bg-[var(--as-glass-bg)] p-5 mb-6">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles size={14} className="text-violet-400" />
              <span className="text-[13px] font-semibold text-[var(--as-text)]">
                Describe your experiment
              </span>
            </div>

            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') void generatePlan()
              }}
              rows={3}
              spellCheck={false}
              placeholder="e.g., Predict customer churn using the uploaded dataset. Compare several models and optimize for recall."
              className="w-full resize-none bg-transparent text-[15px] leading-relaxed text-[var(--as-text)] outline-none placeholder:text-[var(--as-text-3)] border border-[var(--as-border)] rounded-lg px-4 py-3 focus:border-[var(--as-border-hi)] transition-colors"
            />

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-[12px] text-[var(--as-text-3)]">Try:</span>
              {EXAMPLES.map((ex, i) => (
                <button
                  key={i}
                  onClick={() => setDescription(ex)}
                  className="max-w-[200px] truncate rounded-md border border-[var(--as-border)] px-2 py-1 text-[12px] text-[var(--as-text-2)] transition hover:border-[var(--as-border-hi)] hover:bg-[var(--as-glass-bg-2)] hover:text-[var(--as-text)]"
                  title={ex}
                >
                  {ex}
                </button>
              ))}
            </div>

            <div className="mt-4 flex items-center gap-3">
              <button
                onClick={() => void generatePlan()}
                disabled={!description.trim() || loading}
                className="flex h-[36px] items-center gap-2 rounded-lg border border-violet-500 bg-violet-500 px-5 text-[14px] font-semibold text-white transition hover:bg-violet-400 disabled:cursor-not-allowed disabled:border-[var(--as-border)] disabled:bg-[var(--as-glass-bg-2)] disabled:text-[var(--as-text-3)]"
              >
                {loading ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    Generating…
                  </>
                ) : (
                  <>
                    <Zap size={14} />
                    Generate Pipeline
                  </>
                )}
              </button>
              {plan && (
                <button
                  onClick={() => {
                    setPlan(null)
                    setSelectedStage(null)
                    setOriginRunId(null)
                    // Also forget it durably, so returning to this page does
                    // not resurrect a plan the user discarded.
                    clearPipelinePlanDraft()
                  }}
                  className="flex h-[36px] items-center gap-1.5 rounded-lg border border-[var(--as-border)] px-4 text-[13px] text-[var(--as-text-2)] transition hover:bg-[var(--as-glass-bg-2)]"
                >
                  <RotateCcw size={12} />
                  Clear
                </button>
              )}
              <span className="mono text-[11.5px] text-[var(--as-text-3)]">⌘/Ctrl + Enter</span>
            </div>

            {/* Optional planning context. The backend accepts all three; an
                unset field is simply omitted from the request. */}
            <div className="mt-4 grid gap-3 border-t border-[var(--as-border)] pt-4 sm:grid-cols-3">
              <label className="block">
                <span className="label-xs mb-1.5 block">Dataset (optional)</span>
                <input
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                  placeholder="churn.csv"
                  spellCheck={false}
                  className="w-full rounded-lg border border-[var(--as-border)] bg-[var(--as-bg-2)] px-3 py-2 text-[13px] text-[var(--as-text)] outline-none placeholder:text-[var(--as-text-3)] focus:border-[var(--as-accent)]"
                />
              </label>
              <label className="block">
                <span className="label-xs mb-1.5 block">Target column (optional)</span>
                <input
                  value={targetColumn}
                  onChange={(e) => setTargetColumn(e.target.value)}
                  placeholder="churn"
                  spellCheck={false}
                  className="w-full rounded-lg border border-[var(--as-border)] bg-[var(--as-bg-2)] px-3 py-2 text-[13px] text-[var(--as-text)] outline-none placeholder:text-[var(--as-text-3)] focus:border-[var(--as-accent)]"
                />
              </label>
              <label className="block">
                <span className="label-xs mb-1.5 block">Task type (optional)</span>
                <select
                  value={taskType}
                  onChange={(e) => setTaskType(e.target.value)}
                  className="w-full rounded-lg border border-[var(--as-border)] bg-[var(--as-bg-2)] px-3 py-2 text-[13px] text-[var(--as-text)] outline-none focus:border-[var(--as-accent)]"
                >
                  <option value="">Detect automatically</option>
                  <option value="classification">Classification</option>
                  <option value="regression">Regression</option>
                </select>
              </label>
            </div>
          </div>

          {/* ── Error ── */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="mb-6 flex items-start gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3"
              >
                <AlertTriangle size={16} className="text-rose-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-[14px] font-medium text-rose-300">Failed to generate pipeline</p>
                  <p className="text-[13px] text-rose-400/80 mt-0.5">{error}</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Results ── */}
          <AnimatePresence>
            {plan && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 12 }}
                transition={{ duration: 0.3 }}
              >
                {/* Summary bar */}
                <div className="mb-5 flex flex-wrap items-center gap-3">
                  <Badge tone="accent">{plan.task_type}</Badge>
                  <Badge tone="verify">metric: {plan.target_metric}</Badge>
                  <span
                    className={`mono text-[11.5px] px-2 py-0.5 rounded-md border ${complexityBg(plan.complexity)} ${complexityColor(plan.complexity)}`}
                  >
                    {plan.complexity} complexity
                  </span>
                  <span className="mono text-[11.5px] text-[var(--as-text-3)]">
                    {plan.stages.length} stages · {plan.edges.length} connections
                  </span>
                  <span className="mono text-[11.5px] text-[var(--as-text-3)]">
                    source: {plan.source}
                  </span>
                  {originRunId && (
                    <span
                      className="mono text-[11.5px] text-violet-300/90"
                      title="Generated alongside the Generate & Verify session"
                    >
                      from Generate &amp; Verify run {originRunId.slice(0, 8)}
                    </span>
                  )}
                </div>

                {plan.summary && (
                  <p className="mb-5 text-[14px] text-[var(--as-text-2)] leading-relaxed">
                    {plan.summary}
                  </p>
                )}

                {/* Export / hand-off */}
                <div className="mb-4">
                  <PlanActions plan={plan} />
                </div>

                {/* What the plan implies */}
                <div className="mb-5">
                  <PlanAnalysisPanel plan={plan} />
                </div>

                {/* Prepared flow graph, with the stage inspector beneath it */}
                <div className="mb-5">
                  <PlannedPipelineGraph
                    plan={plan}
                    selectedStage={selectedStage}
                    onSelectStage={setSelectedStage}
                  />
                </div>

                {selectedStageData && (
                  <div className="mb-5">
                    <StageDetail stage={selectedStageData} />
                  </div>
                )}

                {/* Assumptions & Risks */}
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {plan.assumptions.length > 0 && (
                    <div className="rounded-xl border border-[var(--as-border)] bg-[var(--as-glass-bg)] p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <Info size={13} className="text-blue-400" />
                        <span className="text-[12.5px] font-semibold text-[var(--as-text)]">
                          Assumptions
                        </span>
                      </div>
                      <ul className="space-y-1.5">
                        {plan.assumptions.map((a, i) => (
                          <li
                            key={i}
                            className="flex items-start gap-2 text-[12.5px] text-[var(--as-text-2)]"
                          >
                            <CheckCircle2 size={12} className="text-blue-400 mt-0.5 shrink-0" />
                            {a}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {plan.risks.length > 0 && (
                    <div className="rounded-xl border border-[var(--as-border)] bg-[var(--as-glass-bg)] p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <AlertTriangle size={13} className="text-amber-400" />
                        <span className="text-[12.5px] font-semibold text-[var(--as-text)]">Risks</span>
                      </div>
                      <ul className="space-y-1.5">
                        {plan.risks.map((r, i) => (
                          <li
                            key={i}
                            className="flex items-start gap-2 text-[12.5px] text-[var(--as-text-2)]"
                          >
                            <AlertTriangle size={12} className="text-amber-400 mt-0.5 shrink-0" />
                            {r}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Empty State ── */}
          {!plan && !loading && !error && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="w-16 h-16 rounded-2xl border border-[var(--as-border)] bg-[var(--as-glass-bg)] flex items-center justify-center mb-4">
                <GitBranch size={24} className="text-[var(--as-text-3)]" />
              </div>
              <p className="text-[16px] font-medium text-[var(--as-text-2)]">
                No pipeline planned yet
              </p>
              <p className="mt-1 max-w-[48ch] text-[14px] text-[var(--as-text-3)] leading-relaxed">
                Describe your experiment above and click Generate Pipeline. The planner will design a
                pipeline with stages, data flow, and agent assignments, and lay it out as a graph.
                Plans started from Generate &amp; Verify appear here automatically.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}