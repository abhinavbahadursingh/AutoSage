/**
 * Cross-page hand-off of a planner result: Generate & Verify → Pipeline.
 *
 * Clicking "Generate & Verify" on the Objectives page kicks off a planner run
 * for the same problem statement, so the Pipeline page shows the project's
 * pipeline as soon as it is opened — no second prompt required.
 *
 * The draft is a *pointer to one plan* held in sessionStorage (same lifetime
 * as the last-run pointer on the Objectives page). Every consumer reads the
 * plan from here rather than re-planning, so the two pages never disagree.
 *
 * Each draft carries an id; subscribers only react to a draft they have not
 * applied yet, so a locally generated plan is never overwritten on remount.
 */

import type { PipelinePlan } from '../data/plannedGraph'

const STORAGE_KEY = 'as_pipeline_plan_draft'

export interface PipelinePlanDraft {
  /** Monotonic per-draft id — lets subscribers ignore replays. */
  id: string
  /** The problem statement the plan was derived from. */
  description: string
  plan: PipelinePlan
  /** Verification run that produced it, when it came from Generate & Verify. */
  runId: string | null
  /** ISO timestamp. */
  createdAt: string
}

type Listener = (draft: PipelinePlanDraft | null) => void

const listeners = new Set<Listener>()

function readStored(): PipelinePlanDraft | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as PipelinePlanDraft
    if (!parsed || typeof parsed.id !== 'string' || !parsed.plan) return null
    return parsed
  } catch {
    /* private mode / quota / corrupt value — treat as "no plan yet" */
    return null
  }
}

let current: PipelinePlanDraft | null = readStored()

/** Latest draft, or null when nothing has been generated this session. */
export function getPipelinePlanDraft(): PipelinePlanDraft | null {
  return current
}

/**
 * Publish a freshly generated plan. Listeners (the Pipeline page) pick it up;
 * the value is also persisted so a reload of that page keeps the plan.
 */
export function setPipelinePlanDraft(
  draft: Omit<PipelinePlanDraft, 'id' | 'createdAt'> & Partial<Pick<PipelinePlanDraft, 'id' | 'createdAt'>>,
): PipelinePlanDraft {
  const next: PipelinePlanDraft = {
    id: draft.id ?? `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    createdAt: draft.createdAt ?? new Date().toISOString(),
    description: draft.description,
    plan: draft.plan,
    runId: draft.runId ?? null,
  }
  current = next
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {
    /* private mode / quota — in-memory copy still serves open pages */
  }
  for (const listener of listeners) listener(next)
  return next
}

/**
 * Subscribe to draft changes. The current value is *not* replayed — callers
 * should read `getPipelinePlanDraft()` once on mount, then subscribe.
 * Returns the unsubscribe function.
 */
export function subscribePipelinePlanDraft(listener: Listener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/**
 * Drop the stored plan (the Pipeline page's Clear action). Consumers that
 * only care about new drafts can ignore the null notification — their local
 * state has already been cleared by then.
 */
export function clearPipelinePlanDraft(): void {
  current = null
  try {
    window.sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    /* nothing durable to clear */
  }
  for (const listener of listeners) listener(null)
}
