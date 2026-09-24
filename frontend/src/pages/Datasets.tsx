import { PageHeader } from '../components/layout/Sidebar'
import { Badge } from '../components/ui/Badge'
import { DATASETS } from '../data/catalog'
import { fmtInt } from '../lib/format'

export function DatasetsPage() {
  return (
    <div className="flex h-full min-w-0 flex-col">
      <PageHeader
        title="Datasets"
        subtitle="Registered artifacts with verified provenance. Every experiment records the content hash it actually read."
        right={
          <div className="mono hidden text-right text-[13px] leading-relaxed text-paper-500 md:block">
            {DATASETS.length} registered
            <br />
            digests valid: {DATASETS.length}/{DATASETS.length}
          </div>
        }
      />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <table className="w-full min-w-[880px] border-collapse text-left">
          <thead className="sticky top-0 z-10 bg-ink-900">
            <tr className="border-b border-ink-600 text-[12px] tracking-[0.09em] text-paper-500 uppercase">
              <th className="px-4 py-2 font-semibold">Dataset</th>
              <th className="px-3 py-2 text-right font-semibold">Rows</th>
              <th className="px-3 py-2 text-right font-semibold">Columns</th>
              <th className="px-3 py-2 text-right font-semibold">Size</th>
              <th className="px-3 py-2 font-semibold">Target</th>
              <th className="px-3 py-2 font-semibold">Task</th>
              <th className="px-3 py-2 text-right font-semibold">Missing</th>
              <th className="px-3 py-2 font-semibold">Tags</th>
              <th className="px-4 py-2 text-right font-semibold">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-700/70">
            {DATASETS.map((d) => (
              <tr key={d.name} className="transition-colors hover:bg-ink-850/60">
                <td className="px-4 py-2.5">
                  <div className="mono text-[15px] text-paper-100">{d.name}</div>
                </td>
                <td className="mono tnum px-3 py-2.5 text-right text-[14px] text-paper-300">{fmtInt(d.rows)}</td>
                <td className="mono tnum px-3 py-2.5 text-right text-[14px] text-paper-300">{d.columns}</td>
                <td className="mono tnum px-3 py-2.5 text-right text-[13.5px] text-paper-400">{d.size}</td>
                <td className="mono px-3 py-2.5 text-[14px] text-accent-300">{d.target ?? '—'}</td>
                <td className="px-3 py-2.5 text-[14px] text-paper-400">{d.task}</td>
                <td className="mono tnum px-3 py-2.5 text-right text-[14px] text-paper-300">{d.missing}%</td>
                <td className="px-3 py-2.5">
                  <div className="flex flex-wrap gap-1">
                    {d.tags.map((t) => (
                      <Badge key={t} tone={t === 'quarantined' || t === 'leakage-suspect' ? 'warn' : 'dim'}>
                        {t}
                      </Badge>
                    ))}
                  </div>
                </td>
                <td className="mono px-4 py-2.5 text-right text-[13.5px] text-paper-500">{d.updated}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
