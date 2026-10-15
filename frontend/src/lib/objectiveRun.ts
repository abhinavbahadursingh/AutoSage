/**
 * Pointer to the current objective-verification run.
 *
 * A *pointer* only — a navigation convenience so pages reached without a run
 * id in the URL (and the Objectives page itself after it unmounts) can find
 * the session that is still in progress. All actual data comes from the
 * backend session record; nothing durable lives in sessionStorage.
 *
 * The pointer is written when a session is created and cleared only when the
 * user starts over (New) or the backend no longer knows the run — tab
 * switches never clear it.
 */

const LAST_RUN_KEY = 'as_objective_run'

/** Record the session a new query just started. */
export function rememberObjectiveRun(runId: string): void {
  try {
    window.sessionStorage.setItem(LAST_RUN_KEY, runId)
  } catch {
    /* private mode / quota — navigation links still carry the run id */
  }
}

/** The session to restore on mount, or null when there is none. */
export function recallObjectiveRun(): string | null {
  try {
    return window.sessionStorage.getItem(LAST_RUN_KEY)
  } catch {
    return null
  }
}

/** Drop the pointer — used on "New" and when the backend no longer knows the run. */
export function forgetObjectiveRun(): void {
  try {
    window.sessionStorage.removeItem(LAST_RUN_KEY)
  } catch {
    /* private mode — there is nothing durable to clear */
  }
}
