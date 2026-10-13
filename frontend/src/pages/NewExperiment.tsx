import { useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { CornerDownLeft, Cpu, Database, FileUp, Gauge, Loader2, ShieldCheck, Sparkles, X, Zap } from 'lucide-react'
import { useStore } from '../store/context'
import { DatasetUploadDialog } from '../components/datasets/DatasetUploadDialog'
import { api } from '../lib/api'
import type { VerificationLevel } from '../lib/types'

const EXAMPLES = [
  'Predict customer churn using the uploaded dataset. Compare several models and optimize for recall.',
  'Estimate default probability on the Q3 lending file; probabilities must be well calibrated.',
  'Route support tickets to the right team. Allow multiple labels per ticket.',
  'Forecast delivery ETA in minutes and alert if feature drift exceeds PSI 0.2.',
]

const METRICS = [
  { id: 'recall', label: 'Recall' },
  { id: 'precision', label: 'Precision' },
  { id: 'roc_auc', label: 'ROC-AUC' },
  { id: 'f1', label: 'F1' },
  { id: 'accuracy', label: 'Accuracy' },
  { id: 'mae', label: 'MAE' },
  { id: 'rmse', label: 'RMSE' },
  { id: 'log_loss', label: 'Log loss' },
]

const BUDGETS = ['5 fit-min', '12 fit-min', '20 fit-min', '45 fit-min', '90 fit-min']

/** Extensions the backend accepts (mirrors settings.ALLOWED_UPLOAD_TYPES). */
const DATASET_ACCEPT = '.csv,.tsv,.txt,text/csv,application/csv,text/plain'

const LEVELS: { id: VerificationLevel; label: string; hint: string }[] = [
  { id: 'fast', label: 'Fast', hint: 'sampled recompute' },
  { id: 'standard', label: 'Standard', hint: 'full recompute' },
  { id: 'strict', label: 'Strict', hint: 'recompute + replay' },
]

function analyze(prompt: string) {
  const p = prompt.toLowerCase()
  const task = /route|ticket|label|tag/.test(p)
    ? 'multi-label text classification'
    : /eta|forecast|minutes|price|amount|regress/.test(p)
      ? 'regression'
      : /churn|fraud|default|readmit|click|convert|binary|defaulted/.test(p)
        ? 'binary classification'
        : prompt.trim().length > 12
          ? 'tabular supervised (unspecified)'
          : '—'
  const metricHint = /recall/.test(p)
    ? 'recall'
    : /precision/.test(p)
      ? 'precision'
      : /calibrat|probab|auc/.test(p)
        ? 'roc_auc'
        : /eta|minutes|mae/.test(p)
          ? 'mae'
          : /f1/.test(p)
            ? 'f1'
            : 'auto'
  const wantsCompare = /compare|several|multiple|search|tune/.test(p)
  const keywords = ['churn', 'fraud', 'default', 'calibrated', 'drift', 'ticket', 'eta', 'recall', 'leakage'].filter(
    (k) => p.includes(k),
  )
  return { task, metricHint, wantsCompare, keywords }
}

function Control({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode
  label: string
  children: React.ReactNode
}) {
  return (
    <label className="flex min-w-0 flex-col gap-1.5">
      <span className="flex items-center gap-1.5 text-[12px] font-semibold tracking-[0.1em] text-paper-500 uppercase">
        {icon}
        {label}
      </span>
      {children}
    </label>
  )
}

const selectCls =
  'h-[30px] w-full rounded-sm border border-ink-600 bg-ink-850 px-2 text-[15px] text-paper-100 outline-none transition hover:border-ink-500 focus:border-accent-500'

const inputCls = `${selectCls} placeholder:text-paper-500`

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

export function NewExperimentPage() {
  const navigate = useNavigate()
  const { createAndRun, memory, memoryLoading, busy } = useStore()
  // The landing page can hand a drafted prompt over via router state.
  const incoming = (useLocation().state as { prompt?: string } | null)?.prompt
  const [prompt, setPrompt] = useState(incoming?.trim() || EXAMPLES[0])
  // The dataset the user picked. Its filename is the identifier the pipeline
  // resolves against — nothing is hardcoded, so any CSV works.
  const [file, setFile] = useState<File | null>(null)
  const [target, setTarget] = useState('churn')
  const [metric, setMetric] = useState('recall')
  const [budget, setBudget] = useState('12 fit-min')
  const [level, setLevel] = useState<VerificationLevel>('strict')
  const [submitting, setSubmitting] = useState(false)
  // Set when a picked dataset could not be stored; reopens the upload prompt.
  const [failedUpload, setFailedUpload] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const resuming = useRef(false)

  const dataset = file?.name ?? ''

  const analysis = useMemo(() => analyze(prompt), [prompt])
  const memoryHits = memory.filter((m) =>
    analysis.keywords.some((k) => m.tags.join(' ').includes(k) || m.experiment.toLowerCase().includes(k)),
  )

  const onFile = (next: File | null) => {
    setFile(next)
    if (!next) setFailedUpload(null)
  }

  // Create the run under a dataset name resolved by the caller.
  const runWith = async (name: string) => {
    await createAndRun({
      prompt: prompt.trim(),
      dataset: name,
      target,
      metric,
      budget,
      verificationLevel: level,
    })
    navigate('/workspace')
  }

  const submit = async () => {
    if (!prompt.trim() || submitting || busy) return
    setSubmitting(true)
    // An attached dataset is a shortcut, not a requirement: when one is
    // picked we upload it up front so the run never has to ask. Otherwise we
    // start the run with no dataset and the discovery agent asks for one
    // when it executes — see Workspace's dataset upload dialog.
    let name = ''
    if (file) {
      try {
        const stored = await api.uploadDataset(file)
        // The backend sanitizes the filename, so use what it actually stored.
        name = stored.name || file.name
      } catch {
        setFailedUpload(file)
        setSubmitting(false)
        return
      }
    }
    try {
      await runWith(name)
    } catch {
      /* toast already shown by store */
    } finally {
      setSubmitting(false)
    }
  }

  // Retry from the upload dialog after a failed store.
  const onUploaded = async (storedName: string) => {
    if (resuming.current) return
    resuming.current = true
    setFailedUpload(null)
    setSubmitting(true)
    try {
      await runWith(storedName)
    } catch {
      /* toast already shown by store */
    } finally {
      setSubmitting(false)
      resuming.current = false
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto flex max-w-[1180px] flex-col gap-5 px-8 py-8">
        <div className="flex items-end justify-between gap-4">
          <div>
            <div className="label-xs">New experiment</div>
            <h1 className="mt-1 text-[23px] font-semibold tracking-[-0.02em] text-paper-50">
              Describe the task. AutoSage plans the run.
            </h1>
            <p className="mt-1 max-w-[70ch] text-[15px] leading-relaxed text-paper-400">
              The orchestrator compiles your request into a task graph, assigns specialized agents, and verifies claims
              before a pipeline is frozen.
            </p>
          </div>
          <div className="mono hidden shrink-0 text-right text-[13px] leading-relaxed text-paper-500 md:block">
            graph: 9 stages (UI)
            <br />
            agents: 8 available
            <br />
            verification: {level}
            <br />
            budget: {budget} (UI only)
          </div>
        </div>

        <div className="rounded-md border border-ink-600 bg-ink-900">
          <div className="flex items-center justify-between border-b border-ink-700 px-4 py-2">
            <span className="flex items-center gap-2 text-[13.5px] text-paper-400">
              <Sparkles size={12} className="text-accent-400" />
              task console
            </span>
            <span className="mono text-[12.5px] text-paper-500">{prompt.trim().length} chars</span>
          </div>

          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') void submit()
            }}
            rows={5}
            spellCheck={false}
            placeholder="Describe what you want AutoSage to build…"
            className="w-full resize-none bg-transparent px-4 py-3.5 text-[17px] leading-relaxed text-paper-50 outline-none placeholder:text-paper-500"
          />

          <div className="flex flex-wrap items-center gap-2 border-t border-ink-700 px-4 py-2.5">
            <span className="text-[13px] text-paper-500">try:</span>
            {EXAMPLES.map((ex, i) => (
              <button
                key={i}
                onClick={() => setPrompt(ex)}
                className="max-w-[240px] truncate rounded-sm border border-ink-600 px-2 py-[3px] text-[13px] text-paper-400 transition hover:border-ink-400 hover:bg-ink-850 hover:text-paper-200"
                title={ex}
              >
                {ex}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 rounded-md border border-ink-600 bg-ink-900 px-4 py-3.5 md:grid-cols-3 xl:grid-cols-5">
          <Control icon={<Database size={11} />} label="Dataset">
            {file ? (
              <div className="flex h-[30px] items-center gap-1.5 rounded-sm border border-accent-500/50 bg-accent-900/30 px-2">
                <FileUp size={12} className="shrink-0 text-accent-300" />
                <span className="mono min-w-0 flex-1 truncate text-[14px] text-paper-100" title={file.name}>
                  {file.name}
                </span>
                <button
                  type="button"
                  onClick={() => onFile(null)}
                  aria-label="Remove dataset"
                  className="shrink-0 text-paper-500 transition hover:text-paper-100"
                >
                  <X size={12} />
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="flex h-[30px] items-center justify-center gap-1.5 rounded-sm border border-dashed border-ink-500 bg-ink-850 px-2 text-[14px] text-paper-300 transition hover:border-accent-500 hover:text-paper-100"
              >
                <FileUp size={12} />
                Upload file
              </button>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept={DATASET_ACCEPT}
              className="hidden"
              onChange={(e) => onFile(e.target.files?.[0] ?? null)}
            />
            <span className="mono text-[11.5px] text-paper-500">
              {file ? fmtBytes(file.size) : 'CSV · filename is the dataset id'}
            </span>
          </Control>
          <Control icon={<Zap size={11} />} label="Target column">
            <input
              className={inputCls}
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder="target"
              spellCheck={false}
            />
          </Control>
          <Control icon={<Gauge size={11} />} label="Evaluation metric">
            <select className={selectCls} value={metric} onChange={(e) => setMetric(e.target.value)}>
              {METRICS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </Control>
          <Control icon={<Cpu size={11} />} label="Compute budget">
            <select className={selectCls} value={budget} onChange={(e) => setBudget(e.target.value)}>
              {BUDGETS.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
            <span className="mono text-[11.5px] text-paper-500">UI hint · not sent to API</span>
          </Control>
          <Control icon={<ShieldCheck size={11} />} label="Verification level">
            <div className="flex h-[30px] overflow-hidden rounded-sm border border-ink-600">
              {LEVELS.map((l) => (
                <button
                  key={l.id}
                  onClick={() => setLevel(l.id)}
                  title={l.hint}
                  className={`flex-1 border-r border-ink-600 text-[13.5px] transition last:border-r-0 ${
                    level === l.id
                      ? 'bg-accent-900/70 text-accent-300'
                      : 'bg-ink-850 text-paper-400 hover:bg-ink-800 hover:text-paper-200'
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
            <span className="mono text-[11.5px] text-paper-500">UI only · not in API schema</span>
          </Control>
        </div>

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_340px]">
          <div className="rounded-md border border-ink-600 bg-ink-900">
            <div className="border-b border-ink-700 px-4 py-2">
              <span className="label-xs">Preflight</span>
            </div>
            <ul className="divide-y divide-ink-700/70">
              <Preflight
                ok={prompt.trim().length > 24}
                label="Intent parse"
                value={
                  prompt.trim().length > 24
                    ? `${analysis.task} · optimize ${analysis.metricHint}`
                    : 'need a fuller description (24+ chars)'
                }
              />
              <Preflight
                ok={Boolean(dataset)}
                partial={!dataset}
                label="Dataset"
                value={
                  dataset
                    ? `${dataset} · uploading now`
                    : 'not attached — the discovery agent will ask for one'
                }
              />
              <Preflight
                ok={analysis.wantsCompare}
                partial={!analysis.wantsCompare}
                label="Search strategy"
                value={
                  analysis.wantsCompare
                    ? 'multi-model shortlist + pilot CV'
                    : 'single strong default (add “compare several models” to widen search)'
                }
              />
              <Preflight
                ok={memoryHits.length > 0}
                partial={memoryHits.length === 0}
                label="Memory matches"
                value={
                  memoryLoading
                    ? 'searching memory…'
                    : memoryHits.length > 0
                      ? `${memoryHits.length} prior ${memoryHits.length === 1 ? 'entry' : 'entries'} · ${memoryHits[0].experiment}`
                      : 'no close prior — run will start from first principles'
                }
              />
              <Preflight ok label="Backend" value="POST /experiments → start · JWT Bearer" />
            </ul>
          </div>

          <div className="flex flex-col justify-between rounded-md border border-ink-600 bg-ink-900 p-4">
            <div className="space-y-2 text-[14px] leading-relaxed text-paper-400">
              <div className="flex items-center justify-between">
                <span>stages (UI)</span>
                <span className="mono text-paper-200">9</span>
              </div>
              <div className="flex items-center justify-between">
                <span>verification</span>
                <span className="mono text-accent-300">
                  {level} · {LEVELS.find((l) => l.id === level)?.hint}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>budget (UI)</span>
                <span className="mono text-paper-200">{budget}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>metric sent</span>
                <span className="mono text-paper-200">{metric}</span>
              </div>
            </div>

            <button
              onClick={() => void submit()}
              disabled={!prompt.trim() || submitting || busy}
              className="mt-4 flex h-[38px] items-center justify-center gap-2 rounded-sm border border-accent-500 bg-accent-500 text-[16px] font-semibold text-ink-950 transition hover:bg-accent-400 disabled:cursor-not-allowed disabled:border-ink-600 disabled:bg-ink-750 disabled:text-paper-500"
            >
              {submitting || busy ? (
                <>
                  <Loader2 size={13} className="animate-spin" />
                  {file ? 'Uploading…' : 'Starting…'}
                </>
              ) : (
                <>
                  Run Experiment
                  <CornerDownLeft size={13} />
                </>
              )}
            </button>
            <p className="mono mt-2 text-center text-[12px] text-paper-500">
              ⌘/Ctrl + Enter
            </p>
          </div>
        </div>
      </div>

      {failedUpload && (
        <DatasetUploadDialog
          datasetName={failedUpload.name}
          onClose={() => setFailedUpload(null)}
          onUploaded={(name) => void onUploaded(name)}
        />
      )}
    </div>
  )
}

function Preflight({
  ok,
  partial = false,
  label,
  value,
}: {
  ok: boolean
  partial?: boolean
  label: string
  value: string
}) {
  const color = ok ? 'bg-verify-500' : partial ? 'bg-warn-500' : 'bg-conflict-500'
  return (
    <li className="flex items-start gap-2.5 px-4 py-2">
      <span className={`mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full ${color}`} />
      <span className="w-[128px] shrink-0 text-[14px] text-paper-200">{label}</span>
      <span className="mono min-w-0 flex-1 truncate text-[13.5px] text-paper-400" title={value}>
        {value}
      </span>
    </li>
  )
}
