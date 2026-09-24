import { Fragment, useMemo, useState } from 'react'
import { Search, X } from 'lucide-react'
import { PageHeader } from '../components/layout/Sidebar'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/Primitives'
import { useStore } from '../store/context'

export function MemoryPage() {
  const { memory } = useStore()
  const [q, setQ] = useState('')
  const [openId, setOpenId] = useState<string | null>('mem-077')

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return memory
    return memory.filter(
      (m) =>
        m.experiment.toLowerCase().includes(needle) ||
        m.problemType.toLowerCase().includes(needle) ||
        m.datasetCharacteristics.toLowerCase().includes(needle) ||
        m.successfulApproach.toLowerCase().includes(needle) ||
        m.tags.some((t) => t.includes(needle)),
    )
  }, [memory, q])

  return (
    <div className="flex h-full min-w-0 flex-col">
      <PageHeader
        title="Experience Library"
        subtitle="Completed experiments distilled into reusable knowledge — what worked, what failed, and why an entry is worth trusting on the next similar task."
        right={
          <div className="mono hidden shrink-0 text-right text-[13px] leading-relaxed text-paper-500 md:block">
            {memory.length} entries indexed
            <br />
            {memory.reduce((a, m) => a + m.reusedCount, 0)} total reuses
          </div>
        }
      />

      <div className="flex items-center gap-2 border-b border-ink-600 bg-ink-900/70 px-5 py-2.5">
        <div className="relative">
          <Search size={12} className="absolute top-1/2 left-2 -translate-y-1/2 text-paper-500" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search problem type, dataset traits, approach…"
            className="h-[28px] w-[320px] max-w-[60vw] rounded-sm border border-ink-600 bg-ink-850 pr-7 pl-7 text-[15px] text-paper-100 outline-none transition focus:border-accent-500"
          />
          {q && (
            <button
              onClick={() => setQ('')}
              className="absolute top-1/2 right-2 -translate-y-1/2 text-paper-500 hover:text-paper-200"
              aria-label="Clear search"
            >
              <X size={12} />
            </button>
          )}
        </div>
        <span className="mono text-[13px] text-paper-500">
          {rows.length}/{memory.length} entries
        </span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {rows.length === 0 ? (
          <EmptyState
            title="No memory entries match"
            detail="Try a broader term such as “imbalanced”, “calibration” or a dataset name. New entries are written automatically when an experiment completes."
          />
        ) : (
          <table className="w-full min-w-[980px] border-collapse text-left">
            <thead className="sticky top-0 z-10 bg-ink-900">
              <tr className="border-b border-ink-600 text-[12px] tracking-[0.09em] text-paper-500 uppercase">
                <th className="w-[220px] px-4 py-2 font-semibold">Experiment</th>
                <th className="w-[160px] px-3 py-2 font-semibold">Problem type</th>
                <th className="w-[240px] px-3 py-2 font-semibold">Dataset characteristics</th>
                <th className="w-[280px] px-3 py-2 font-semibold">Successful approach</th>
                <th className="w-[200px] px-3 py-2 font-semibold">Failed approaches</th>
                <th className="w-[90px] px-3 py-2 font-semibold">Confidence</th>
                <th className="w-[70px] px-3 py-2 text-right font-semibold">Reused</th>
                <th className="w-[100px] px-4 py-2 text-right font-semibold">Last used</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-700/70">
              {rows.map((m) => {
                const open = openId === m.id
                return (
                  <Fragment key={m.id}>
                    <tr
                      onClick={() => setOpenId(open ? null : m.id)}
                      className={`cursor-pointer align-top transition-colors ${
                        open ? 'bg-ink-850' : 'hover:bg-ink-850/60'
                      }`}
                    >
                      <td className="px-4 py-2.5">
                        <div className="text-[15px] leading-snug font-medium text-paper-100">{m.experiment}</div>
                        <div className="mono mt-0.5 text-[12.5px] text-paper-500">{m.id}</div>
                      </td>
                      <td className="px-3 py-2.5 text-[14px] leading-snug text-paper-300">{m.problemType}</td>
                      <td className="px-3 py-2.5 text-[13.5px] leading-snug text-paper-400">{m.datasetCharacteristics}</td>
                      <td className="px-3 py-2.5 text-[13.5px] leading-snug text-paper-300">{m.successfulApproach}</td>
                      <td className="px-3 py-2.5">
                        <ul className="flex flex-col gap-1">
                          {m.failedApproaches.map((f, i) => (
                            <li key={i} className="flex items-start gap-1.5 text-[13px] leading-snug text-paper-500">
                              <span className="mt-[5px] h-1 w-1 shrink-0 rounded-full bg-conflict-500/80" />
                              <span className="line-clamp-2">{f}</span>
                            </li>
                          ))}
                        </ul>
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-1.5">
                          <span className="mono tnum text-[14px] text-paper-100">{m.confidence.toFixed(2)}</span>
                          <span className="h-[3px] w-8 overflow-hidden rounded-full bg-ink-700">
                            <span
                              className={`block h-full ${m.confidence >= 0.8 ? 'bg-verify-500' : m.confidence >= 0.5 ? 'bg-warn-500' : 'bg-conflict-500'}`}
                              style={{ width: `${m.confidence * 100}%` }}
                            />
                          </span>
                        </div>
                      </td>
                      <td className="mono tnum px-3 py-2.5 text-right text-[14px] text-paper-200">{m.reusedCount}</td>
                      <td className="mono px-4 py-2.5 text-right text-[13.5px] text-paper-400">{m.lastUsed}</td>
                    </tr>
                    {open && (
                      <tr className="bg-ink-900">
                        <td colSpan={8} className="px-4 pb-4">
                          <div className="anim-fade-in grid grid-cols-1 gap-4 rounded-md border border-ink-600 bg-ink-850/60 p-3.5 lg:grid-cols-[1fr_260px]">
                            <div>
                              <div className="label-xs mb-1.5">Why this entry is useful</div>
                              <p className="text-[15px] leading-relaxed text-paper-200">{m.whyUseful}</p>
                              <div className="mt-3 flex flex-wrap gap-1.5">
                                {m.tags.map((t) => (
                                  <Badge key={t} tone="dim">
                                    {t}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                            <div className="border-t border-ink-700 pt-3 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-4">
                              <div className="label-xs mb-1.5">Failed approaches (detail)</div>
                              <ul className="flex flex-col gap-1.5">
                                {m.failedApproaches.map((f, i) => (
                                  <li key={i} className="text-[13.5px] leading-relaxed text-paper-400">
                                    {f}
                                  </li>
                                ))}
                              </ul>
                              <div className="mono mt-3 text-[12.5px] text-paper-500">
                                promoted from {m.experiment ? 'source run' : '—'} · reuse counter {m.reusedCount}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
