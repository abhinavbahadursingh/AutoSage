import { useMemo, useState } from 'react'
import { PageHeader } from '../components/layout/Sidebar'
import { Badge } from '../components/ui/Badge'
import { KeyVal } from '../components/ui/Primitives'
import { AGENT_ROSTER, STAGE_META } from '../data/experiments'
import { fmtMs } from '../lib/format'
import type { AgentNode } from '../lib/types'
import { useStore } from '../store/context'

function agentStages(agentName: string, nodes: AgentNode[]) {
  return nodes.filter((n) => n.agent === agentName)
}

export function AgentsPage() {
  const { activeExperiment } = useStore()
  const [selected, setSelected] = useState(AGENT_ROSTER[1].name)

  const rows = useMemo(
    () =>
      AGENT_ROSTER.map((a) => {
        const stages = agentStages(a.name, activeExperiment.nodes)
        const done = stages.filter((s) => s.state === 'done')
        const active = stages.find((s) => s.state === 'active')
        const conf = done.length ? done.reduce((sum, s) => sum + s.confidence, 0) / done.length : null
        const ms = done.reduce((sum, s) => sum + (s.elapsedMs ?? 0), 0)
        const tools = done.reduce((sum, s) => sum + s.tools.length, 0)
        return {
          ...a,
          stages,
          done,
          active,
          conf,
          ms,
          tools,
          state: active ? 'running' : done.length === stages.length && stages.length > 0 ? 'idle-done' : 'idle',
        }
      }),
    [activeExperiment],
  )

  const current = rows.find((r) => r.name === selected) ?? rows[0]
  const currentNodes = current.stages

  return (
    <div className="flex h-full min-w-0 flex-col">
      <PageHeader
        title="Agents"
        subtitle="The eight autonomous workers assigned to every task graph. Status reflects the currently open experiment."
        right={
          <div className="mono hidden text-right text-[13px] leading-relaxed text-paper-500 md:block">
            8 agents available
            <br />
            verification engine online
          </div>
        }
      />

      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1 overflow-y-auto">
          <table className="w-full min-w-[640px] border-collapse text-left">
            <thead className="sticky top-0 z-10 bg-ink-900">
              <tr className="border-b border-ink-600 text-[12px] tracking-[0.09em] text-paper-500 uppercase">
                <th className="px-4 py-2 font-semibold">Agent</th>
                <th className="px-3 py-2 font-semibold">Role</th>
                <th className="px-3 py-2 font-semibold">Stages</th>
                <th className="px-3 py-2 font-semibold">State</th>
                <th className="px-3 py-2 text-right font-semibold">Avg conf.</th>
                <th className="px-3 py-2 text-right font-semibold">Tools</th>
                <th className="px-4 py-2 text-right font-semibold">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-700/70">
              {rows.map((r) => (
                <tr
                  key={r.id}
                  onClick={() => setSelected(r.name)}
                  className={`cursor-pointer transition-colors ${
                    selected === r.name ? 'bg-ink-850' : 'hover:bg-ink-850/60'
                  }`}
                >
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          r.state === 'running'
                            ? 'animate-pulse bg-accent-400'
                            : r.state === 'idle-done'
                              ? 'bg-verify-500'
                              : 'bg-ink-500'
                        }`}
                      />
                      <span className="text-[15.5px] font-medium text-paper-100">{r.name}</span>
                    </div>
                  </td>
                  <td className="mono px-3 py-2.5 text-[13.5px] text-paper-400">{r.role}</td>
                  <td className="px-3 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {r.stages.map((s) => {
                        const meta = STAGE_META.find((m) => m.id === s.stage)
                        return (
                          <span
                            key={s.id}
                            title={meta?.label}
                            className={`mono rounded-sm border px-1 py-[1px] text-[11.5px] tracking-[0.05em] ${
                              s.state === 'done'
                                ? 'border-verify-500/35 text-verify-500/90'
                                : s.state === 'active'
                                  ? 'border-accent-500/50 text-accent-300'
                                  : 'border-ink-600 text-paper-500'
                            }`}
                          >
                            {meta?.short}
                          </span>
                        )
                      })}
                      {r.stages.length === 0 && <span className="text-[13.5px] text-paper-500">—</span>}
                    </div>
                  </td>
                  <td className="px-3 py-2.5">
                    <Badge tone={r.state === 'running' ? 'accent' : r.state === 'idle-done' ? 'verify' : 'dim'}>
                      {r.state === 'running' ? 'running' : r.state === 'idle-done' ? 'completed' : 'standby'}
                    </Badge>
                  </td>
                  <td className="mono tnum px-3 py-2.5 text-right text-[14px] text-paper-200">
                    {r.conf !== null ? r.conf.toFixed(2) : '—'}
                  </td>
                  <td className="mono tnum px-3 py-2.5 text-right text-[14px] text-paper-300">
                    {r.tools || '—'}
                  </td>
                  <td className="mono tnum px-4 py-2.5 text-right text-[13.5px] text-paper-400">
                    {r.ms ? fmtMs(r.ms) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <aside className="hidden w-[320px] shrink-0 overflow-y-auto border-l border-ink-600 bg-ink-900 xl:block">
          <div className="border-b border-ink-600 px-4 py-3">
            <h2 className="text-[16px] font-semibold text-paper-50">{current.name}</h2>
            <div className="mono mt-0.5 text-[12.5px] text-paper-500">{current.role}</div>
          </div>

          <div className="border-b border-ink-700 px-4 py-1">
            <KeyVal k="experiment" v={activeExperiment.id} />
            <KeyVal k="stages owned" v={String(current.stages.length)} />
            <KeyVal k="avg confidence" v={current.conf !== null ? current.conf.toFixed(2) : '—'} />
            <KeyVal k="tools called" v={String(current.tools)} />
            <KeyVal k="cpu time" v={current.ms ? fmtMs(current.ms) : '—'} />
          </div>

          <div className="px-4 py-3">
            <div className="label-xs mb-2">Stage log</div>
            {currentNodes.length === 0 ? (
              <p className="text-[14px] leading-relaxed text-paper-500">
                This agent does not own a stage in the current task graph layout — it acts as fallback when a peer
                agent times out.
              </p>
            ) : (
              <ul className="flex flex-col gap-2.5">
                {currentNodes.map((n) => {
                  const meta = STAGE_META.find((m) => m.id === n.stage)
                  return (
                    <li key={n.id} className="rounded-sm border border-ink-700 bg-ink-850/70 p-2.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[14px] text-paper-100">{meta?.label}</span>
                        <Badge tone={n.state === 'done' ? 'verify' : n.state === 'active' ? 'accent' : 'dim'}>
                          {n.state}
                        </Badge>
                      </div>
                      <p className="mt-1.5 text-[13.5px] leading-relaxed text-paper-400">
                        {n.state === 'idle' ? n.idleAction : n.action}
                      </p>
                      <div className="mono mt-1.5 text-[12.5px] text-paper-500">
                        conf {n.confidence.toFixed(2)} · {n.tools.length} tools
                        {n.elapsedMs ? ` · ${fmtMs(n.elapsedMs)}` : ''}
                      </div>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}
