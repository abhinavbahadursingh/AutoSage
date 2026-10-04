import { useEffect, useState } from 'react'
import { PageHeader } from '../components/layout/Sidebar'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/Primitives'
import { api, ApiError, type ProjectResponse } from '../lib/api'

interface DatasetRow {
  id: string
  name: string
  rows?: number | null
  columns?: number | null
  size?: string | null
  target?: string | null
  task?: string | null
  missing?: number | null
  updated?: string | null
  tags?: string[]
}

export function DatasetsPage() {
  const [projects, setProjects] = useState<ProjectResponse[] | null>(null)
  const [datasets, setDatasets] = useState<DatasetRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const list = await api.listProjects()
        if (cancelled) return
        setProjects(list)
        // Backend project datasets endpoint returns [] today — still call it honestly.
        if (list.length > 0) {
          try {
            const ds = await api.listDatasets(list[0].id)
            if (!cancelled) setDatasets((ds as DatasetRow[]) ?? [])
          } catch {
            if (!cancelled) setDatasets([])
          }
        } else {
          setDatasets([])
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Failed to load datasets')
          setProjects([])
          setDatasets([])
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="flex h-full min-w-0 flex-col">
      <PageHeader
        title="Datasets"
        subtitle="Registered artifacts from the backend projects/datasets endpoints. Empty lists mean the registry has no rows yet — no mock catalog is shown."
        right={
          <div className="mono hidden text-right text-[13px] leading-relaxed text-paper-500 md:block">
            {projects?.length ?? 0} projects
            <br />
            {datasets.length} datasets
          </div>
        }
      />
      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <EmptyState title="Loading datasets…" detail="GET /projects → GET /projects/{id}/datasets" />
        ) : error ? (
          <EmptyState title="Could not load datasets" detail={error} />
        ) : datasets.length === 0 ? (
          <EmptyState
            title="No datasets registered"
            detail={
              projects && projects.length > 0
                ? `Found ${projects.length} project(s) but the datasets endpoint returned an empty list.`
                : 'No projects exist yet. Datasets will appear when the backend registry has entries.'
            }
          />
        ) : (
          <table className="w-full min-w-[880px] border-collapse text-left">
            <thead className="sticky top-0 z-10 bg-ink-900">
              <tr className="border-b border-ink-600 text-[12px] tracking-[0.09em] text-paper-500 uppercase">
                <th className="px-4 py-2 font-semibold">Dataset</th>
                <th className="px-3 py-2 text-right font-semibold">Rows</th>
                <th className="px-3 py-2 text-right font-semibold">Columns</th>
                <th className="px-3 py-2 text-right font-semibold">Size</th>
                <th className="px-3 py-2 font-semibold">Target</th>
                <th className="px-3 py-2 font-semibold">Task</th>
                <th className="px-4 py-2 text-right font-semibold">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-700/70">
              {datasets.map((d) => (
                <tr key={d.id} className="transition-colors hover:bg-ink-850/60">
                  <td className="mono px-4 py-2.5 text-[15px] text-paper-100">{d.name}</td>
                  <td className="mono tnum px-3 py-2.5 text-right text-[14px] text-paper-300">
                    {d.rows != null ? d.rows.toLocaleString('en-US') : '—'}
                  </td>
                  <td className="mono tnum px-3 py-2.5 text-right text-[14px] text-paper-300">
                    {d.columns ?? '—'}
                  </td>
                  <td className="mono tnum px-3 py-2.5 text-right text-[13.5px] text-paper-400">{d.size ?? '—'}</td>
                  <td className="mono px-3 py-2.5 text-[14px] text-accent-300">{d.target ?? '—'}</td>
                  <td className="px-3 py-2.5 text-[14px] text-paper-400">{d.task ?? '—'}</td>
                  <td className="mono px-4 py-2.5 text-right text-[13.5px] text-paper-500">{d.updated ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {projects && projects.length > 0 && (
          <div className="border-t border-ink-700 px-5 py-3">
            <div className="label-xs mb-2">Projects</div>
            <div className="flex flex-wrap gap-2">
              {projects.map((p) => (
                <Badge key={p.id} tone="dim">
                  {p.name}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
