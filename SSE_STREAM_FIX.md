# Objective Verification SSE Stream Fix

## Problem

After clicking "Generate & Verify" on the Objectives page, the SSE stream connected but immediately ended (`SSE stream ended (reader done)`) without delivering any verification frames. The page stayed stuck on "Waiting on real backend progress..." with `busy=true` forever, because:

1. **No `onStage`/`onReport`/`onError` callback ever fired** — the stream closed before any frame was delivered.
2. **No reconnection or fallback** — the frontend had no recovery path when the server closed the stream prematurely.

## Root Cause

The SSE stream endpoint (`stream_session` in `backend/app/api/v1/endpoints/objective_verification.py`) used the **same SQLAlchemy `AsyncSession` object** (`session: DbSession`) across every poll tick of the `event_source()` generator.

Meanwhile, the verification run commits its frames from a **background task's own session** (`_dispatch` → `execute_session` → `_persist` → `await self.session.commit()`).

SQLAlchemy's `AsyncSession.get()` returns objects from its identity map without re-querying the database. While the code called `expire_all()` before each re-read, the same session object was held open across all ticks. In practice this meant:

- The stream's session could hold a stale identity-map snapshot of the `VerificationSession` row.
- Frames committed by the background task's session were not visible to the stream's session.
- With no new frames and no terminal status, the stream yielded `: waiting` keep-alives — but if the session appeared to already be terminal (e.g. verification completed before the client connected, which can happen in <2 seconds when codegen fails fast), the stream yielded the terminal frame and closed immediately.
- If the terminal frame was large or the connection closed before it was fully flushed, the frontend received nothing: no `onReport`, no `onError`, just `reader done`.

## Changes

### Backend: `backend/app/api/v1/endpoints/objective_verification.py`

**`stream_session` endpoint:**

1. **Removed the `session: DbSession` parameter** from the stream function signature. The request-scoped session is no longer held open for the entire stream lifetime.

2. **Initial ownership check uses a fresh session** from `_session_factory()` — opened, used for the 404 ownership check, then closed immediately.

3. **`event_source()` opens a fresh database session for every poll tick** — `async with session_factory() as poll_session:` inside the `while True` loop. Each tick:
   - Reads the `VerificationSession` row from a brand-new session, guaranteeing visibility of the latest committed frames from the background task.
   - Yields any new frames (replaying from `sent` offset).
   - Yields `: waiting` keep-alive when there's nothing new.
   - Returns when the run reaches `FAILED` or `COMPLETED` (with report).

This eliminates the SQLAlchemy identity-map staleness entirely: every poll is an independent read committed after the background task's writes.

### Frontend: `frontend/src/lib/api.ts`

**`streamObjectiveSession`:**

- Added an optional `onEnd?: () => void` handler.
- Called when the server closes the stream normally (reader done) without an error and without the client aborting.
- The page can use this to reconnect or fall back to polling.

### Frontend: `frontend/src/pages/Objectives.tsx`

**`subscribe` callback:**

- `onOpen` resets the reconnect budget (`reconnectRef.current = { count: 0, max: 5 }`).
- New `onEnd` handler:
  - Attempts up to 5 reconnections (1 second apart).
  - If reconnection is exhausted, falls back to polling `api.getObjectiveSession(id)`:
    - If a report exists → shows it.
    - If status is `FAILED` → shows the error.
    - Otherwise → shows a "stream ended" error.
  - Sets `busy=false` and `connected=false` in all terminal paths so the page never stays stuck on "Waiting on real backend progress...".

**New `reconnectRef`** (`useRef({ count: 0, max: 5 })`) — tracks reconnect attempts per session, reset on each new `onOpen`.

## Data Flow After Fix

```
Client clicks "Generate & Verify"
    ↓
POST /objective-verification/sessions  →  run_id returned immediately
    ↓
Background task _dispatch starts:
    - Sets status = RUNNING, commits
    - Runs run_verification (emits frames via _persist, commits each)
    - Sets status = COMPLETED + report, commits
    ↓
Client connects to SSE stream:
    - Fresh ownership check session (opened + closed)
    - event_source() loop:
        - Fresh poll session per tick → reads latest row
        - Yields all stored frames (replay from offset 0)
        - Yields ": waiting" keep-alive every 0.2s while running
        - Yields terminal frame (report or error) when done
    ↓
Client receives frames → applyFrame → updates timeline/logs
    ↓
onReport → setReport, setBusy(false), shows final verdict
OR
onEnd → reconnect (up to 5x) → fallback poll getObjectiveSession
```

## Verification

All 149 backend unit tests pass, including the 3 SSE stream freshness tests:

- `test_stream_sees_progress_made_after_it_subscribed` — frames committed while the stream is open reach the client
- `test_stream_reports_failure_and_stops` — a failed run yields an error frame and terminates
- `test_stream_keeps_sending_keepalives_during_a_silent_gap` — idle ticks emit `: waiting` comment frames

## Files Changed

| File | Change |
|------|--------|
| `backend/app/api/v1/endpoints/objective_verification.py` | Fresh DB session per poll tick; removed long-lived request session from stream |
| `frontend/src/lib/api.ts` | Added `onEnd` handler to `streamObjectiveSession` |
| `frontend/src/pages/Objectives.tsx` | Reconnection logic (max 5 attempts) + fallback to `getObjectiveSession` polling |
| `backend/tests/unit/test_objective_stream_freshness.py` | Updated to patch `_SESSION_FACTORY` instead of passing a session directly |
