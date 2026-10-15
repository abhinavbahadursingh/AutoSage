import { AlertTriangle, Clock, Gauge, GitBranch, Layers, Timer, Workflow } from 'lucide-react'
import type { PipelinePlan } from '../../data/plannedGraph'
import { analyzePlan, formatMinutes } from '../../data/planAnalysis'

function Metric({
  icon: Icon,
  label,
  value,
  hint,
  tone = 'default',
}: {
  icon: typeof Clock
  label: string
  value: string
  hint?: string
  tone?: 'default' | 'warn' | 'good'
}) {
  const color =
    tone === 'warn' ? 'var(--as-warn)' : tone === 'good' ? 'var(--as-verify)' : 'var(--as-text)'
  return (
    <div className="rounded-xl border border-[var(--as-border)] bg-[var(--as-glass-bg)] px-3.5 py-3">
      <div className="mb-1.5 flex items-center gap-1.5">
        <Icon size={12} style={{ color: 'var(--as-text-3)' }} aria-hidden />
        <span className="label-xs">{label}</span>
      </div>
      <p className="mono text-[17px] font-semibold leading-tight" style={{ color }}>
        {value}
      </p>
      {hint && <p className="mt-1 text-[11px] leading-snug text-[var(--as-text-3)]">{hint}</p>}
    </div>
  )
}

/**
 * What the plan implies, computed from it.
 *
 * Durations are the planner's own estimates; the parallelism and critical-path
 * figures are arithmetic over those estimates and the edge list. When a stage
 * has no parseable duration the critical path is withheld rather than guessed.
 */
export function PlanAnalysisPanel({ plan }: { plan: PipelinePlan }) {
  const a = analyzePlan(plan)
  const stageById = new Map(plan.stages.map((s) => [s.id, s]))

  const hasTime = a.serialMinutes !== null
  const hasCritical = a.criticalMinutes !== null && a.criticalPath.length > 0

  // Speedup only means something when both totals exist and differ.
  const speedup =
    a.serialMinutes !== null && a.parallelMinutes !== null && a.parallelMinutes > 0
      ? a.serialMinutes / a.parallelMinutes
      : null

  const criticalHint = (): string => {
    if (!hasCritical || !a.criticalPath.length) return 'Needs a duration on every stage'
    const names = a.criticalPath.map((id) => stageById.get(id)?.name ?? id)
    const head = names.slice(0, 3).join(' → ')
    return names.length > 3 ? `${head} → …` : head
  }

  return (
    <div className="rounded-2xl border border-[var(--as-border)] bg-[var(--as-glass-bg)] p-4">
      <div className="mb-3 flex items-center gap-2">
        <Gauge size={13} className="text-[var(--as-teal)]" aria-hidden />
        <span className="text-[12.5px] font-semibold text-[var(--as-text)]">What this plan implies</span>
        <span className="mono ml-auto text-[10.5px] text-[var(--as-text-3)]">
          {a.complexitySignals.join(' · ')}
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric
          icon={Clock}
          label="Serial total"
          value={formatMinutes(a.serialMinutes)}
          hint={
            hasTime
              ? `Sum of all ${plan.stages.length} stage estimates`
              : 'The planner did not quantify every stage'
          }
          tone={hasTime ? 'default' : 'warn'}
        />
        <Metric
          icon={Timer}
          label="Critical path"
          value={formatMinutes(a.criticalMinutes)}
          hint={criticalHint()}
          tone={hasCritical ? 'good' : 'warn'}
        />
        <Metric
          icon={Layers}
          label="Parallelism"
          value={`${a.maxParallel} wide`}
          hint={
            a.maxParallel > 1
              ? `Up to ${a.maxParallel} stages can run at once${speedup ? ` · ~${speedup.toFixed(1)}× speedup` : ''}`
              : 'Strictly sequential — no stage branches'
          }
          tone={a.maxParallel > 1 ? 'good' : 'default'}
        />
        <Metric
          icon={a.gaps.length > 0 ? AlertTriangle : Workflow}
          label="Data-flow links"
          value={a.gaps.length === 0 ? 'all linked' : `${a.gaps.length} unlinked`}
          hint={
            a.gaps.length === 0
              ? 'Every non-entry input and non-final output is connected'
              : `${a.gaps.filter((g) => g.kind === 'unresolved_input').length} inputs no stage produces · ${a.gaps.filter((g) => g.kind === 'unused_output').length} outputs nothing consumes`
          }
          tone={a.gaps.length > 0 ? 'warn' : 'good'}
        />
      </div>

      {/* Agent roster */}
      {a.agents.length > 0 && (
        <div className="mt-3 border-t border-[var(--as-border)] pt-3">
          <div className="mb-2 flex items-center gap-1.5">
            <GitBranch size={11} style={{ color: 'var(--as-text-3)' }} aria-hidden />
            <span className="label-xs">Agents involved</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {a.agents.map((agent) => (
              <span
                key={agent.name}
                className="mono rounded-lg border border-[var(--as-border)] px-2 py-1 text-[11px] text-[var(--as-text-2)]"
              >
                {agent.name}
                <span className="ml-1.5 text-[var(--as-text-3)]">
                  {agent.stages} stage{agent.stages === 1 ? '' : 's'}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Data-flow gaps, named explicitly so the user can act on them */}
      {a.gaps.length > 0 && (
        <div className="mt-3 border-t border-[var(--as-border)] pt-3">
          <div className="mb-2 flex items-center gap-1.5">
            <AlertTriangle size={11} style={{ color: 'var(--as-warn)' }} aria-hidden />
            <span className="label-xs">Unlinked data</span>
          </div>
          <ul className="space-y-1">
            {a.gaps.map((g, i) => (
              <li key={`${g.stageId}-${g.item}-${i}`} className="flex items-start gap-2 text-[11.5px]">
                <span className="mono shrink-0 text-[var(--as-text-3)]">
                  {stageById.get(g.stageId)?.name ?? g.stageId}
                </span>
                <span className="text-[var(--as-warn)]">
                  {g.kind === 'unresolved_input' ? 'input not produced by any upstream stage:' : 'output not consumed downstream:'}{' '}
                  <span className="mono text-[var(--as-text-2)]">{g.item}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}