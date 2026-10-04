# AutoSage — launch video plan (`/brag-slim`)

**Input:** Project (`D:\autoSage`) · **Tone:** `default` (punchy, playful, clean) · **Format:** landscape 1920×1080, 30 fps · **Duration:** 20.0 s (600 frames)

---

## 1. What it is

AutoSage is a verified multi-agent AutoML system: you describe an ML problem in plain
English, and specialized LangGraph agents turn it into a pipeline that is empirically
tested and independently verified before it is frozen.

**Who it's for:** ML engineers and data scientists who don't trust black-box AutoML.
**What it does for them:** answers "why this pipeline?" with an inspectable evidence trail
instead of a leaderboard number.
**What sets it apart:** the empirical verification gate — generated code and model outcomes
pass AST security analysis, leakage checks, metric sanity and baseline dominance before
acceptance; every decision is recorded in an immutable `Agent → Decision → Evidence → Result` DAG.
**Most impressive claim:** the system argues with itself — a Verifier recomputes the claims
the agents just made, and only then does the pipeline get frozen.
**Visual hook:** the real dark-charcoal UI with its single orange accent, drifting geometric
line figures (hexagons, φ, grid nodes) and the 9-stage execution timeline lighting up.
**Real flow shown:** entry → key action → result, entirely with the shipped React components:
`NewExperimentPage` (type a prompt, preflight goes green, Run) → `WorkspacePage` +
`ExecutionTimeline` (9 stages tick over) → `AgentDrawer` (reasoning → evidence) →
verification, metrics, claims → `HomePage` hero.
**Tone:** `default` — punchy, playful, clean. Soft dips through the background between beats.
**Share caption:** "Type a sentence, get an ML pipeline that has already argued with itself.
AutoSage runs 9 stages across 8 agents, then a verifier recomputes every claim."

---

## 2. Angle, hook, highlights, punchline

- **Angle:** the product *doing the job*, not a landing page describing it. One continuous
  demo run, cut into four beats with a caption above the app.
- **Hook (0–3.3 s):** the prompt types itself into the real task console —
  "Predict customer churn using the uploaded dataset. Compare several models and optimize
  for recall." — the preflight checklist goes green row by row, cursor lands on
  **Run Experiment**, click. No title card; the UI *is* the hook.
- **Highlight 1 (3.4–7.7 s):** reveal — the workspace, sidebar and 9-stage timeline; stages
  tick green one at a time while the current-activity panel narrates each agent.
  Caption: **"Nine stages. Eight agents. One prompt."**
- **Highlight 2 (7.8–13.1 s):** agents show their work — camera pushes in, the Verifier's
  `AgentDrawer` slides open on *Reasoning*, then flips to *Evidence*: verification proof,
  evidence rows, audit block. Caption: **"Every decision leaves an inspectable trail."**
- **Highlight 3 (13.2–16.5 s):** it checks itself — status flips to COMPLETED / VERIFIED,
  metrics count up, and the claims panel slides in with 3 verified claims.
  Caption: **"Claims recomputed independently."**
- **Punchline (16.6–20.0 s):** the real hero line, rising in: **"From a question to a
  verified ML pipeline."** + wordmark + process rail.

---

## 3. Visual identity (taken from the code, not invented)

| | |
|---|---|
| Surfaces | `ink-900 #0b0c0e`, `ink-950 #08090a`, panels `ink-900` / `ink-850 #0e1013` |
| Type | Playfair Display (display/serif, the app's `--font-sans`), JetBrains Mono (`.mono`) |
| Accent | single orange `#f97316 / #ff9f43`, used sparingly |
| States | verify `#3ecf8e`, warn `#e0a33e`, conflict `#e2725b` |
| Motif | `BackgroundField` — drifting grid + orange line polygons (hex, pent, φ, grid-node) |
| Radii / density | 2–6 px radii, hairline borders, small uppercase labels |

Everything on screen comes from the shipped app: `NewExperimentPage`, `WorkspacePage`,
`ExecutionTimeline`, `AgentDrawer`, `Sidebar`/`Logo`, `Badge`, `ToastHost`,
`BackgroundField`, `HomePage` — plus `deriveNodes()` / `STAGE_META` for the real stage
graph and the app's own copy (`IDLE_TEXT`, Home's `JOURNEY`/`CONCEPTS`, claim texts from
`backend/app/engine/verification/claims.py`).

---

## 4. Storyboard (durations sum to 20.0 s)

| # | Scene | Time | Dur | What happens | Camera |
|---|---|---|---|---|---|
| 1 | **Hook — "describe it"** | 0.00–3.30 | 3.30 | Real task console; prompt types in (0.35→2.45); preflight rows flip to green (1.4→2.6); cursor glides to *Run Experiment* and presses (2.75→3.10); dip through background | 1.00 → 1.03 push-in, centred |
| 2 | **Reveal — "it runs"** | 3.42–7.70 | 4.28 | Workspace cuts in: `RUNNING`, sidebar `engine online` + progress; stages REQ→DISC→PROF→PREP→SEL tick green (3.60, 4.45, 5.30, 6.15, 7.00); activity panel narrates each agent; caption in at 3.75, out at 7.35 | app at `top:110` so the caption owns the top band |
| 3 | **Agents show their work** | 7.82–13.05 | 5.23 | Dip → camera pushes in on timeline + activity; TRAIN (8.25) then EVAL (9.95) tick over; `AgentDrawer` slides in at 11.00 on the **Verifier** (Reasoning tab: action, decision, confidence bar); tab flips to **Evidence** at 12.00 (verification proof, evidence rows, audit); caption 8.25→12.55 | scale 1.32, focused on activity panel |
| 4 | **It checks itself** | 13.17–16.45 | 3.28 | Dip → pulled back; VERIFICATION stage runs, PIPELINE freezes at 14.05; at **14.55** status flips COMPLETED + VERIFIED (badges, sidebar progress 100 %) and metrics count up (recall / precision / roc_auc); success toast at 14.70; claims panel slides up at 15.20 with 3 VERIFIED claims; caption 13.55→16.05 | scale 1.00, full workspace |
| 5 | **Punchline** | 16.57–20.00 | 3.43 | Dip → real `HomePage` hero rises: kicker "AUTO SAGE / VERIFIED MULTI-AGENT AUTOML", H1 *"From a question to a verified ML pipeline."*, paragraph, CTA row, process rail with travelling dot; hold to 20.00 | 1.00 → 1.015 slow push |

Cut points: **3.36 / 7.76 / 13.11 / 16.51** — each is a 0.12 s gap where the app dips to
the `BackgroundField` alone (no muddy crossfades; old content out, background, new content in).

---

## 5. Sound

One piece, one key (F♯ minor), 120 BPM, written as music + effects together — effects are
in the same space and sit softly under the mix.

| Time | Music | Effect (blended, -12 dB under bed) |
|---|---|---|
| 0.0–3.3 | sparse sub + filtered pad, no drums | typing ticks (each keystroke, very soft), a low **thock** on the button press at 3.0 |
| 3.4–7.8 | beat enters: kick, closed hats, bass pulse, arp | soft **whoosh** on the reveal cut; a small blip as each stage turns green |
| 7.8–13.1 | arp widens, pad opens, hats double | rising whoosh on the push-in; a light **click** when the drawer opens; a two-note pluck when the Evidence tab flips |
| 13.2–16.5 | adds a 3-note **verify chime** on the VERIFIED flip, filter opens | gentle riser 16.0→16.5; claim rows land with soft ticks |
| 16.5–20.0 | final chord + sub hit on the hero, pad tail | long reverb tail, fade to silence by 20.0 |

Mix: music bed ≈ -14 LUFS-ish, effects 10–12 dB under it, soft-knee limiter, no clipping,
nothing harsh or spiky; repeated ticks stay in the background.

---

## 6. Build

- **Renderer:** a second Vite entry `frontend/brag.html` → `src/brag/*` that mounts the
  project's *real* components with a mock store (`Ctx.Provider` + `MemoryRouter`), driven by
  `window.__setTime(t)`. Every frame is a pure function of time: `flushSync` render →
  `document.getAnimations()` seeked to the scene-local clock and paused → screenshot.
- **Capture:** `playwright-core` + Edge headless, 1920×1080, 600 JPEG frames at 30 fps.
- **Audio:** synthesised with numpy (oscillators, filtered noise, convolution reverb),
  mixed, then muxed with ffmpeg (imageio-ffmpeg binary).
- **Deliverables:** `brag.mp4` (poster baked into frame 0), `brag.jpg`, `share-copy.txt`.

### Note on numbers
Metric values, evidence rows and agent decisions shown in the run are **illustrative demo
output for the telco churn dataset** — the product's own UI text (stage names, actions,
preflight rows, claim texts, headlines) is taken verbatim from the repository.
