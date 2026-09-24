import { Plus, Search } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useMemo, useState } from 'react'
import { PageHeader } from '../components/layout/Sidebar'
import { Badge } from '../components/ui/Badge'
import { statusTone } from '../lib/tones'
import { EmptyState } from '../components/ui/Primitives'
import { useStore } from '../store/context'

export function ExperimentsPage() {
  const { experiments, openExperiment } = useStore()
  const navigate = useNavigate()
  const [q, setQ] = useState('')

  const rows = useMemo(() => {
    const n = q.trim().toLowerCase()
    if (!n) return experiments
    return experiments.filter(
      (e) =>
        e.name.toLowerCase().includes(n) ||
        e.dataset.toLowerCase().includes(n) ||
        e.id.includes(n) ||
        e.prompt.toLowerCase().includes(n),
    )
  }, [experiments, q])

  const open = (id: string) => {
    openExperiment(id)
    navigate('/workspace')
  }

  return (
    <div className="flex h-full min-w-0 flex-col">
      <PageHeader
        title="Experiments"
        subtitle="Every run recorded in this workspace, with its verification outcome. Click a row to load it into the experiment workspace."
        right={
          <button
            onClick={() => navigate('/new')}
            className="flex h-[28px] items-center gap-1.5 rounded-sm border border-accent-500 bg-accent-500 px-2.5 text-[14px] font-medium text-ink-950 transition hover:bg-accent-400"
          >
            <Plus size={13} /> New Experiment
          </button>
        }
      />

      <div className="flex items-center gap-2 border-b border-ink-600 bg-ink-900/70 px-5 py-2.5">
        <div className="relative">
          <Search size={12} className="absolute top-1/2 left-2 -translate-y-1/2 text-paper-500" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter by name, dataset, id…"
            className="h-[28px] w-[280px] rounded-sm border border-ink-600 bg-ink-850 pr-2 pl-7 text-[15px] text-paper-100 outline-none transition focus:border-accent-500"
          />
        </div>
        <span className="mono text-[13px] text-paper-500">{rows.length} runs</span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {rows.length === 0 ? (
          <EmptyState title="No experiments match" detail="Clear the filter or start a new experiment." />
        ) : (
          <table className="w-full min-w-[900px] border-collapse text-left">
            <thead className="sticky top-0 z-10 bg-ink-900">
              <tr className="border-b border-ink-600 text-[12px] tracking-[0.09em] text-paper-500 uppercase">
                <th className="px-4 py-2 font-semibold">Experiment</th>
                <th className="px-3 py-2 font-semibold">Status</th>
                <th className="px-3 py-2 font-semibold">Dataset</th>
                <th className="px-3 py-2 font-semibold">Objective</th>
                <th className="px-3 py-2 font-semibold">Model</th>
                <th className="px-3 py-2 text-right font-semibold">Runtime</th>
                <th className="px-3 py-2 font-semibold">Verification</th>
                <th className="px-4 py-2 text-right font-semibold">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-700/70">
              {rows.map((e) => (
                <tr
                  key={e.id}
                  onClick={() => open(e.id)}
                  className="cursor-pointer transition-colors hover:bg-ink-850/60"
                >
                  <td className="max-w-[300px] px-4 py-2.5">
                    <div className="truncate text-[15.5px] font-medium text-paper-100">{e.name}</div>
                    <div className="mono mt-0.5 truncate text-[12.5px] text-paper-500">
                      {e.id} · {e.owner}
                    </div>
                  </td>
                  <td className="px-3 py-2.5">
                    <Badge tone={statusTone(e.status)}>{e.status}</Badge>
                  </td>
                  <td className="mono max-w-[170px] truncate px-3 py-2.5 text-[13.5px] text-paper-300" title={e.dataset}>
                    {e.dataset}
                  </td>
                  <td className="px-3 py-2.5 text-[14px] text-paper-400">
                    target <span className="mono text-paper-200">{e.target}</span> ·{' '}
                    <span className="mono text-paper-200">{e.metric}</span>
                  </td>
                  <td className="mono max-w-[180px] truncate px-3 py-2.5 text-[13.5px] text-paper-300">{e.model}</td>
                  <td className="mono tnum px-3 py-2.5 text-right text-[13.5px] text-paper-300">{e.runtime}</td>
                  <td className="px-3 py-2.5">
                    <Badge tone={statusTone(e.verificationStatus)}>{e.verificationStatus}</Badge>
                  </td>
                  <td className="mono px-4 py-2.5 text-right text-[13px] text-paper-500">{e.createdAt}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
