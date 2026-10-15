import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, Download, FileJson, FileText, GitBranch, Rocket } from 'lucide-react'
import type { PipelinePlan } from '../../data/plannedGraph'
import { planToMarkdown, planToMermaid } from '../../data/planAnalysis'

type Format = 'markdown' | 'mermaid' | 'json'

function serialize(plan: PipelinePlan, format: Format): string {
  if (format === 'markdown') return planToMarkdown(plan)
  if (format === 'mermaid') return planToMermaid(plan)
  return JSON.stringify(plan, null, 2)
}

function filename(plan: PipelinePlan, format: Format): string {
  const base = (plan.summary || plan.task_type || 'pipeline')
    .slice(0, 40)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  const ext = format === 'markdown' ? 'md' : format === 'mermaid' ? 'mmd' : 'json'
  return `${base || 'pipeline'}-plan.${ext}`
}

const BUTTONS: Array<{ format: Format; label: string; icon: typeof FileText }> = [
  { format: 'markdown', label: 'Markdown', icon: FileText },
  { format: 'mermaid', label: 'Mermaid', icon: GitBranch },
  { format: 'json', label: 'JSON', icon: FileJson },
]

/**
 * Turn a plan into something the user can keep: copy or download it in a
 * portable format, or hand the description to the experiment composer.
 */
export function PlanActions({ plan }: { plan: PipelinePlan }) {
  const [copied, setCopied] = useState<Format | null>(null)
  const navigate = useNavigate()

  const copy = useCallback(async (format: Format) => {
    const text = serialize(plan, format)
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // Clipboard is blocked in some contexts; fall back to a selectable prompt.
      window.prompt(`Copy the ${format} plan:`, text)
    }
    setCopied(format)
    window.setTimeout(() => setCopied((c) => (c === format ? null : c)), 1800)
  }, [plan])

  const download = useCallback(
    (format: Format) => {
      const blob = new Blob([serialize(plan, format)], {
        type: format === 'json' ? 'application/json' : 'text/plain',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename(plan, format)
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    },
    [plan],
  )

  return (
    <div className="flex flex-wrap items-center gap-2">
      {BUTTONS.map(({ format, label, icon: Icon }) => (
        <div key={format} className="flex items-center gap-1">
          <button
            onClick={() => void copy(format)}
            className="btn-ghost flex h-7 items-center gap-1.5 rounded-lg px-2.5 text-[11.5px]"
            title={`Copy the plan as ${label}`}
          >
            {copied === format ? (
              <Check size={11} className="text-[var(--as-verify)]" />
            ) : (
              <Icon size={11} />
            )}
            {copied === format ? 'Copied' : label}
          </button>
          <button
            onClick={() => download(format)}
            aria-label={`Download ${label}`}
            title={`Download the plan as ${label}`}
            className="flex h-7 w-7 items-center justify-center rounded-lg border border-[var(--as-border)] text-[var(--as-text-2)] transition hover:bg-[var(--as-glass-bg-2)] hover:text-[var(--as-text)]"
          >
            <Download size={11} />
          </button>
        </div>
      ))}

      {/* The description is the only thing the composer needs; carry it across
          so the user does not retype it. */}
      <button
        onClick={() =>
          navigate('/new', {
            state: {
              prompt: `${plan.summary || plan.task_type}\n\nTarget metric: ${plan.target_metric}`,
            },
          })
        }
        className="btn-primary ml-auto flex h-7 items-center gap-1.5 rounded-lg px-3 text-[11.5px]"
        title="Open this plan in the experiment composer"
      >
        <Rocket size={11} />
        Start this experiment
      </button>
    </div>
  )
}