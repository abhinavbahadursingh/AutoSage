import type { StageId } from '../lib/types'

export const FPS = 30
export const DURATION = 20
export const WIDTH = 1920
export const HEIGHT = 1080
/** Height of the caption band that sits above the app in scenes 2–4. */
export const BAND = 110

export const PROMPT =
  'Predict customer churn using the uploaded dataset. Compare several models and optimize for recall.'

export type SceneId = 'hook' | 'run' | 'agents' | 'verify' | 'hero'

export interface Scene {
  id: SceneId
  /** visual start (fade-in begins) */
  t0: number
  /** fade-out start */
  tOut: number
  /** fully gone / unmounts */
  t1: number
  /** caption above the app (scenes 2–4) */
  band: boolean
  fadeIn: number
}

export const SCENES: Scene[] = [
  { id: 'hook', t0: 0, tOut: 3.12, t1: 3.3, band: false, fadeIn: 0.45 },
  { id: 'run', t0: 3.42, tOut: 7.52, t1: 7.7, band: true, fadeIn: 0.18 },
  { id: 'agents', t0: 7.82, tOut: 13.07, t1: 13.25, band: true, fadeIn: 0.18 },
  { id: 'verify', t0: 13.37, tOut: 16.27, t1: 16.45, band: true, fadeIn: 0.18 },
  { id: 'hero', t0: 16.57, tOut: 19.99, t1: 20.02, band: false, fadeIn: 0.3 },
]

export function sceneAt(t: number): Scene | null {
  for (const s of SCENES) if (t >= s.t0 && t < s.t1) return s
  return null
}

export function sceneOpacity(s: Scene, t: number): number {
  const inn = Math.min(1, Math.max(0, (t - s.t0) / s.fadeIn))
  const out = Math.min(1, Math.max(0, (s.t1 - t) / (s.t1 - s.tOut)))
  return Math.min(inn, out)
}

/* ---------------------------------------------------------------- run clock */

export const STAGE_ORDER: StageId[] = [
  'request',
  'discovery',
  'profiling',
  'preprocessing',
  'selection',
  'training',
  'evaluation',
  'verification',
  'pipeline',
]

export const STAGE_START: Record<StageId, number> = {
  request: 3.6,
  discovery: 4.45,
  profiling: 5.3,
  preprocessing: 6.15,
  selection: 7.0,
  training: 8.25,
  evaluation: 9.95,
  verification: 10.9,
  pipeline: 13.9,
}

export const STAGE_END: Record<StageId, number> = {
  request: 4.45,
  discovery: 5.3,
  profiling: 6.15,
  preprocessing: 7.0,
  selection: 8.25,
  training: 9.95,
  evaluation: 10.9,
  verification: 13.9,
  pipeline: 14.4,
}

export const EXPERIMENT_AT = 3.42
export const RUN_AT = 3.6
export const COMPLETE_AT = 14.4
/** Demo runs tick at this multiple of wall time so the elapsed clock reads plausibly. */
export const ELAPSED_SPEED = 6

export function liveStageAt(t: number): StageId | null {
  if (t < RUN_AT || t >= COMPLETE_AT) return null
  for (const s of STAGE_ORDER) if (t >= STAGE_START[s] && t < STAGE_END[s]) return s
  return null
}

export function doneStagesAt(t: number): StageId[] {
  return STAGE_ORDER.filter((s) => t >= STAGE_END[s])
}

export function statusAt(t: number): 'QUEUED' | 'RUNNING' | 'COMPLETED' | null {
  if (t < EXPERIMENT_AT) return null
  if (t < RUN_AT) return 'QUEUED'
  if (t < COMPLETE_AT) return 'RUNNING'
  return 'COMPLETED'
}

export function elapsedMsAt(t: number): number {
  return Math.max(0, (t - RUN_AT) * ELAPSED_SPEED * 1000)
}

export function elapsedLabelAt(t: number): string {
  const ms = elapsedMsAt(t)
  const total = Math.floor(ms / 1000)
  const mm = String(Math.floor(total / 60)).padStart(2, '0')
  const ss = String(total % 60).padStart(2, '0')
  return `${mm}:${ss}.${Math.floor((ms % 1000) / 100)}`
}

export function runtimeLabel(): string {
  const total = Math.round((COMPLETE_AT - RUN_AT) * ELAPSED_SPEED)
  return `${Math.floor(total / 60)}m ${String(total % 60).padStart(2, '0')}s`
}

/* ------------------------------------------------------------ hook timings */

export const TYPE_IN = 0.35
export const TYPE_OUT = 2.45
export const CURSOR_IN = 2.3
export const CURSOR_AT_BUTTON = 2.86
export const PRESS_AT = 2.92
export const PRESS_OUT = 3.08
export const CURSOR_OUT = 3.12

export function promptAt(t: number): string {
  if (t <= TYPE_IN) return ''
  if (t >= TYPE_OUT) return PROMPT
  const p = (t - TYPE_IN) / (TYPE_OUT - TYPE_IN)
  return PROMPT.slice(0, Math.round(p * PROMPT.length))
}

/* ----------------------------------------------------------- caption beats */

export interface Caption {
  t0: number
  t1: number
  text: string
}

export const CAPTIONS: Caption[] = [
  { t0: 3.75, t1: 7.52, text: 'Nine stages. Eight agents. One prompt.' },
  { t0: 8.15, t1: 12.9, text: 'Every decision leaves an inspectable trail.' },
  { t0: 14.25, t1: 16.27, text: 'Claims recomputed independently.' },
]

/* --------------------------------------------------------- scene 3 / 4 bits */

export const DRAWER_AT = 11.0
export const EVIDENCE_TAB_AT = 11.95
export const CLAIMS_AT = 15.15
export const CLAIMS_OUT = 16.27
export const METRICS_FROM = 14.4
export const METRICS_TO = 15.45
