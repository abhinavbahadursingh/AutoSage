/**
 * Workspace picker for a fresh verification session.
 *
 * Lists only the caller's own workspaces. A verification session belongs to
 * exactly one, and the backend rejects any other id with a 404, so this never
 * proposes a workspace the session could not be created in.
 */
import { useEffect, useState } from 'react'

import { api, ApiError, type WorkspaceRead } from '../../lib/api'

export function WorkspaceSelect({
  value,
  onChange,
}: {
  value: string
  onChange: (workspaceId: string) => void
}) {
  const [workspaces, setWorkspaces] = useState<WorkspaceRead[]>([])
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void api
      .listWorkspaces(1, 100)
      .then((page) => {
        if (cancelled) return
        setWorkspaces(page.items ?? [])
        setFailed(false)
        // Preselect the caller's only workspace; with several, leave the
        // choice to them rather than guessing.
        if (page.items?.length === 1) onChange(page.items[0].id)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setFailed(err instanceof ApiError)
        setWorkspaces([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // `onChange` is intentionally excluded: it is a setState wrapper from the
    // parent and including it would re-fetch on every parent render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const label = 'Workspace'

  if (loading) {
    return (
      <label className="flex flex-col gap-1">
        <span className="label-xs" style={{ color: 'var(--as-text-3)' }}>
          {label}
        </span>
        <div className="h-[30px] animate-pulse rounded-sm" style={{ background: 'var(--as-bg-3)' }} />
      </label>
    )
  }

  if (failed || workspaces.length === 0) {
    return (
      <label className="flex flex-col gap-1">
        <span className="label-xs" style={{ color: 'var(--as-text-3)' }}>
          {label}
        </span>
        <div
          className="rounded-sm border px-2.5 py-1.5 text-[13px]"
          style={{ borderColor: 'var(--as-border)', color: 'var(--as-text-3)' }}
        >
          {failed
            ? 'Could not load your workspaces.'
            : 'No workspace yet. Create one from the Workspace page, then start a verification.'}
        </div>
      </label>
    )
  }

  return (
    <label className="flex flex-col gap-1">
      <span className="label-xs" style={{ color: 'var(--as-text-3)' }}>
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-[30px] rounded-sm border px-2 text-[13.5px] outline-none"
        style={{
          borderColor: 'var(--as-border-hi)',
          background: 'var(--as-bg-2)',
          color: 'var(--as-text)',
        }}
      >
        <option value="">Select a workspace…</option>
        {workspaces.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name}
          </option>
        ))}
      </select>
    </label>
  )
}