import { useState } from 'react'
import { Pause, Play, RotateCcw, Square } from 'lucide-react'
import { useStore } from '../store/context'
import { Badge } from '../components/ui/Badge'
import { statusTone } from '../lib/tones'
import { ExecutionTimeline } from '../components/workspace/ExecutionTimeline'
import { AgentDrawer } from '../components/workspace/AgentDrawer'
import { STAGE_META } from '../data/experiments'
import { fmtMs } from '../lib/format'

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-[12.5px] tracking-[0.1em] text-paper-500 uppercase">{label}</span>
      <span className="mono truncate text-[15px] text-paper-100" title={value}>
        {value}
      </span>
    </div>
  )
}

function ControlButton({
  children,
  onClick,
  primary = false,
  danger = false,
}: {
  children: React.ReactNode
  onClick: () => void
  primary?: boolean
  danger?: boolean
}) {
  return (
    <button
      onClick={onClick}
      className={`flex h-[30px] items-center gap-1.5 rounded-sm border px-3 text-[15px] font-medium transition-colors ${
        primary
          ? 'border-accent-500 bg-accent-500 text-ink-950 hover:border-accent-400 hover:bg-accent-400'
          : danger
            ? 'border-ink-500 bg-ink-850 text-conflict-500 hover:border-conflict-500/60'
            : 'border-ink-500 bg-ink-850 text-paper-200 hover:border-ink-400 hover:bg-ink-800'
      }`}
    >
      {children}
    </button>
  )
}

export function WorkspacePage() {
  const { activeExperiment, selectedNodeId, setSelectedNodeId, run, pause, resume, stop, runState, elapsedLabel } =
    useStore()
  const [drawerOpen, setDrawerOpen] = useState(false)

  const exp = activeExperiment
  const isRunning = exp.status === 'running' && runState.id === exp.id
  const selectedNode = exp.nodes.find((n) => n.id === selectedNodeId) ?? null

  const activeIdx = isRunning ? runState.stageIndex : exp.status === 'completed' ? exp.nodes.length - 1 : -1
  const activityNode = exp.nodes[activeIdx] ?? null

  const metrics = exp.result
    ? [
        { label: 'PR-AUC', value: (exp.result.metrics.find((m) => m.name === 'PR-AUC')?.value ?? 0).toFixed(3) },
        { label: 'ROC-AUC', value: (exp.result.metrics.find((m) => m.name === 'ROC-AUC')?.value ?? 0).toFixed(3) },
        {
          label: 'Recall',
          value: `${((exp.result.metrics.find((m) => m.name === 'Recall')?.value ?? 0) * 100).toFixed(1)}%`,
        },
      ]
    : [
        { label: 'PR-AUC', value: '—' },
        { label: 'ROC-AUC', value: '—' },
        { label: 'Recall', value: '—' },
      ]

  const openNode = (id: string) => {
    setSelectedNodeId(id)
    setDrawerOpen(true)
  }

  return (
    <div className="relative h-full overflow-y-auto">
      <div className="mx-auto flex min-h-full w-full flex-col px-8 pt-8 pb-7">
        {/* title + status */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="max-w-[46ch] text-[25px] leading-tight font-semibold tracking-[-0.02em] text-paper-50">
                {exp.name}
              </h1>
              <Badge tone={statusTone(exp.status)}>
                {isRunning && <span className="h-1 w-1 animate-pulse rounded-full bg-accent-400" />}
                {exp.status}
              </Badge>
              <Badge tone={statusTone(exp.verificationStatus)}>{exp.verificationStatus}</Badge>
            </div>
            <p className="mono mt-2 max-w-[54ch] truncate text-[14px] text-paper-500" title={exp.prompt}>
              {exp.id} · {exp.prompt}
            </p>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {isRunning ? (
              <>
                {runState.paused ? (
                  <ControlButton onClick={resume}>
                    <Play size={12} /> Resume
                  </ControlButton>
                ) : (
                  <ControlButton onClick={pause}>
                    <Pause size={12} /> Pause
                  </ControlButton>
                )}
                <ControlButton danger onClick={stop}>
                  <Square size={11} /> Stop
                </ControlButton>
              </>
            ) : (
              <ControlButton primary onClick={() => run(exp.id)}>
                <RotateCcw size={12} />
                {exp.status === 'completed' ? 'Re-run' : 'Run experiment'}
              </ControlButton>
            )}
          </div>
        </div>

        {/* meta */}
        <div className="mt-5 flex flex-wrap items-center gap-x-7 gap-y-2 border-y border-ink-700 py-3">
          <MetaItem label="Dataset" value={exp.dataset} />
          <MetaItem label="Model" value={exp.model} />
          <MetaItem label="Runtime" value={isRunning ? elapsedLabel : exp.runtime} />
          <MetaItem label="Metric" value={exp.metric} />
          <MetaItem label="Budget" value={exp.budget} />
        </div>

        {/* timeline */}
        <section className="mt-8">
          <div className="mb-4 flex items-center justify-between">
            <span className="label-xs">Execution</span>
            <span className="mono text-[13px] text-paper-500">
              {exp.nodes.filter((n) => n.state === 'done').length}/{exp.nodes.length} stages
              {isRunning ? ' · running' : ''}
            </span>
          </div>
          <ExecutionTimeline experiment={exp} selectedId={selectedNodeId} onSelect={openNode} />
        </section>

        {/* metrics */}
        <section className="mt-9 grid grid-cols-3 border-y border-ink-700">
          {metrics.map((m, i) => (
            <div key={m.label} className={`py-6 ${i > 0 ? 'border-l border-ink-700 pl-7' : ''}`}>
              <div className="text-[12.5px] tracking-[0.14em] text-paper-500 uppercase">{m.label}</div>
              <div className="mono tnum mt-2 text-[35.5px] leading-none font-medium text-paper-50">{m.value}</div>
            </div>
          ))}
        </section>

        {/* current activity */}
        <section className="mt-9 flex min-h-0 flex-1 flex-col">
          <div className="mb-3 flex items-center justify-between">
            <span className="label-xs">Current activity</span>
            <span className="mono text-[13px] text-paper-500">
              {activityNode ? `stage ${STAGE_META[exp.nodes.indexOf(activityNode)]?.label.toLowerCase()}` : 'idle'}
            </span>
          </div>

          <div className="flex min-h-[160px] flex-1 flex-col rounded-md border border-ink-600 bg-ink-900 px-5 py-4">
            {!activityNode ? (
              <div className="my-auto py-3">
                <p className="text-[16.5px] text-paper-200">No active run</p>
                <p className="mt-1.5 max-w-[62ch] text-[15.5px] leading-relaxed text-paper-500">
                  Start the experiment to watch agents work through the task graph. Each stage records its decision,
                  evidence and verification result — inspect any step from the timeline above.
                </p>
              </div>
            ) : (
              <div className="flex flex-1 items-center">
                <div className="flex w-full items-start gap-4">
                  <span
                    className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                      isRunning ? 'animate-pulse bg-accent-400' : 'bg-verify-500'
                    }`}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span className="text-[16.5px] font-medium text-paper-50">{activityNode.agent}</span>
                      <span className="mono text-[13.5px] text-paper-500">
                        conf {activityNode.confidence.toFixed(2)}
                        {activityNode.elapsedMs ? ` · ${fmtMs(activityNode.elapsedMs)}` : ''}
                      </span>
                      <Badge tone={statusTone(activityNode.verification.status)}>
                        {activityNode.verification.status}
                      </Badge>
                    </div>
                    <p className="mt-2 max-w-[80ch] text-[16px] leading-relaxed text-paper-300">
                      {isRunning ? activityNode.action : activityNode.decision}
                    </p>
                    <button
                      onClick={() => openNode(activityNode.id)}
                      className="mt-3 flex items-center gap-1 text-[15px] text-accent-400 transition hover:text-accent-300"
                    >
                      Inspect this agent →
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>

        <p className="mt-7 max-w-[92ch] text-[14px] leading-relaxed text-paper-500">
          Click any point in the execution timeline to open its full record — reasoning, evidence, tool calls,
          verification proofs and analysis appear only when you ask for them.
        </p>
      </div>

      {drawerOpen && selectedNode && (
        <AgentDrawer experiment={exp} node={selectedNode} onClose={() => setDrawerOpen(false)} />
      )}
    </div>
  )
}
