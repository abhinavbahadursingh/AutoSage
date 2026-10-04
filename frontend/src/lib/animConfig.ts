/**
 * AutoSage Animation Config
 * ─────────────────────────
 * Single source of truth for all animation timing, easing, and intensity.
 *
 * TUNING GUIDE
 * • intensity: 'low' | 'medium' | 'high'
 *   - low:    simple fades only, no parallax, no cursor effects, no particles
 *   - medium: reveals + tilt + cursor, no particles/trail
 *   - high:   everything on
 *
 * • Change INTENSITY below to dial up/down the whole site at once.
 */

export type AnimIntensity = 'low' | 'medium' | 'high'

// ── Master intensity dial ─────────────────────────────────────────────────────
export const INTENSITY: AnimIntensity = 'high'

// ── Easing curves ─────────────────────────────────────────────────────────────
export const EASE = {
  /** Main reveal / entrance easing */
  out:      [0.22, 1, 0.36, 1] as [number, number, number, number],
  /** Snappy micro-interaction */
  snap:     [0.34, 1.56, 0.64, 1] as [number, number, number, number],
  /** Linear for looping */
  linear:   [0, 0, 1, 1] as [number, number, number, number],
  /** Ease-in for exits */
  in:       [0.55, 0, 1, 0.45] as [number, number, number, number],
} as const

// ── Duration presets (ms → seconds for Framer Motion) ─────────────────────────
export const DUR = {
  micro:   0.15,
  fast:    0.25,
  normal:  0.55,
  reveal:  0.75,
  slow:    1.1,
  crawl:   2.0,
} as const

// ── Stagger delay between children ───────────────────────────────────────────
export const STAGGER = {
  tight:  0.04,
  normal: 0.08,
  loose:  0.14,
} as const

// ── Scroll reveal defaults ────────────────────────────────────────────────────
export const REVEAL = {
  /** How far below viewport edge to start trigger (0 = right when enters) */
  threshold: 0.15,
  /** Initial y offset for fade-up */
  yOffset: 32,
  /** Initial blur */
  blur: '6px',
} as const

// ── Tilt card settings ────────────────────────────────────────────────────────
export const TILT = {
  maxDeg:    8,
  scalePeak: 1.02,
  speed:     0.1,
} as const

// ── Cursor settings ───────────────────────────────────────────────────────────
export const CURSOR = {
  dotSize:    6,
  ringSize:   36,
  ringExpand: 56,
  lerpFactor: 0.12,
  lerpDot:    0.35,
} as const

// ── Particle / node network ───────────────────────────────────────────────────
export const PARTICLES = {
  count:       55,
  connectDist: 130,
  speed:       0.35,
  dotRadius:   1.8,
} as const

// ── Lenis scroll ──────────────────────────────────────────────────────────────
export const LENIS = {
  lerp:     0.1,
  duration: 1.2,
  smoothWheel: true,
  /**
   * REQUIRED: every app page scrolls inside its own inner overflow container
   * (body is overflow:hidden, so the window never scrolls). Without this,
   * Lenis preventDefaults all wheel events and mouse-scroll dies everywhere.
   * With it, Lenis yields to natively-scrollable nested containers.
   */
  allowNestedScroll: true,
} as const

// ── Feature flags derived from intensity ─────────────────────────────────────
export function getFlags(intensity: AnimIntensity = INTENSITY) {
  return {
    scrollReveals:    true,                          // always on
    parallax:         intensity !== 'low',
    cursor:           intensity !== 'low',
    tilt:             intensity !== 'low',
    particles:        intensity === 'high',
    trail:            intensity === 'high',
    magnetic:         intensity !== 'low',
    typewriter:       true,                          // always on
    numberCounters:   true,                          // always on
    pageTransitions:  intensity !== 'low',
  }
}

/** True when the OS prefers reduced motion. Call inside components/hooks. */
export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}
