import { PageHeader } from '../components/layout/Sidebar'
import { Badge } from '../components/ui/Badge'
import { statusTone } from '../lib/tones'
import { MODELS } from '../data/catalog'

export function ModelsPage() {
  return (
    <div className="flex h-full min-w-0 flex-col">
      <PageHeader
        title="Models"
        subtitle="Frozen pipelines produced by verified experiments. Champion models are eligible for promotion after a second successful reuse."
        right={
          <div className="mono hidden text-right text-[13px] leading-relaxed text-paper-500 md:block">
            {MODELS.filter((m) => m.status === 'production').length} in production
            <br />
            {MODELS.filter((m) => m.status === 'champion').length} champion
          </div>
        }
      />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <table className="w-full min-w-[860px] border-collapse text-left">
          <thead className="sticky top-0 z-10 bg-ink-900">
            <tr className="border-b border-ink-600 text-[12px] tracking-[0.09em] text-paper-500 uppercase">
              <th className="px-4 py-2 font-semibold">Pipeline</th>
              <th className="px-3 py-2 font-semibold">Family</th>
              <th className="px-3 py-2 font-semibold">Task</th>
              <th className="px-3 py-2 text-right font-semibold">Score</th>
              <th className="px-3 py-2 font-semibold">Metric</th>
              <th className="px-3 py-2 font-semibold">Source run</th>
              <th className="px-4 py-2 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-700/70">
            {MODELS.map((m) => (
              <tr key={m.name} className="transition-colors hover:bg-ink-850/60">
                <td className="mono px-4 py-2.5 text-[15px] text-paper-100">{m.name}</td>
                <td className="px-3 py-2.5 text-[14px] text-paper-300">{m.family}</td>
                <td className="px-3 py-2.5 text-[14px] text-paper-400">{m.task}</td>
                <td className="mono tnum px-3 py-2.5 text-right text-[15px] text-paper-100">
                  {m.score === 0 ? '—' : m.score.toFixed(3)}
                </td>
                <td className="mono px-3 py-2.5 text-[13.5px] text-accent-300">{m.metric}</td>
                <td className="mono px-3 py-2.5 text-[13.5px] text-paper-400">{m.trainedOn}</td>
                <td className="px-4 py-2.5">
                  <Badge tone={statusTone(m.status)}>
                    {m.status}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="px-4 py-3 text-[13.5px] leading-relaxed text-paper-500">
          Scores are the primary metric of the originating experiment, measured on the verified holdout split. Archived
          models remain addressable for audit but are excluded from routing.
        </p>
      </div>
    </div>
  )
}
