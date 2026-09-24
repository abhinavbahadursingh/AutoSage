import type { AgentNode, Experiment } from '../../lib/types'

const STEPS: { label: string }[] = [
  { label: 'Request' },
  { label: 'Dataset' },
  { label: 'Profile' },
  { label: 'Prepare' },
  { label: 'Model' },
  { label: 'Train' },
  { label: 'Evaluate' },
  { label: 'Verify' },
  { label: 'Pipeline' },
]

function dotClass(state: AgentNode['state']) {
  if (state === 'done') return 'border-verify-500 bg-verify-500'
  if (state === 'active') return 'border-accent-400 bg-accent-400 anim-node-pulse'
  if (state === 'queued') return 'border-ink-400 bg-ink-900'
  if (state === 'failed') return 'border-conflict-500 bg-conflict-500'
  return 'border-ink-500 bg-ink-900'
}

export function ExecutionTimeline({
  experiment,
  selectedId,
  onSelect,
}: {
  experiment: Experiment
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const nodes = experiment.nodes

  return (
    <div className="flex items-start justify-between gap-0 overflow-x-auto pb-1">
      {nodes.map((node, i) => {
        const step = STEPS[i] ?? { label: node.stage }
        const selected = selectedId === node.id
        const filled = i > 0 && nodes[i - 1].state === 'done' && node.state !== 'idle'
        return (
          <div key={node.id} className="flex min-w-[76px] flex-1 items-center last:min-w-0">
            <button
              onClick={() => onSelect(node.id)}
              title={`${step.label} — ${node.agent}`}
              className="group flex flex-col items-center gap-2 outline-none"
            >
              <span
                className={`relative h-[9px] w-[9px] rounded-full border transition-all duration-300 ${dotClass(node.state)} ${
                  selected ? 'ring-2 ring-accent-400/40 ring-offset-2 ring-offset-ink-900' : ''
                }`}
              />
              <span
                className={`text-[13px] tracking-[0.01em] transition-colors ${
                  node.state === 'active'
                    ? 'text-accent-300'
                    : selected
                      ? 'text-paper-50'
                      : node.state === 'done'
                        ? 'text-paper-300'
                        : 'text-paper-500 group-hover:text-paper-300'
                }`}
              >
                {step.label}
              </span>
            </button>
            {i < nodes.length - 1 && (
              <span
                className={`mx-1 h-px flex-1 transition-colors duration-500 ${
                  filled ? 'bg-verify-500/45' : 'bg-ink-700'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
