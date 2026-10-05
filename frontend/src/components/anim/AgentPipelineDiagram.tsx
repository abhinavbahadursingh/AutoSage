/**
 * AgentPipelineDiagram — sticky storytelling section.
 * As the user scrolls through the tall track, agents light up one by one
 * and the SVG connecting lines draw themselves via pathLength.
 *
 * Container-aware: progress is derived from the track's bounding rect
 * against the viewport (works with window scroll AND inner overflow
 * scroll containers), not from framer-motion's window-only useScroll.
 */
import { useEffect, useRef } from 'react'
import { motion, useMotionValue, useTransform } from 'framer-motion'
import { prefersReducedMotion } from '../../lib/animConfig'

const AGENTS = [
  { id: 'planner',  label: 'Planner',       icon: '◈', desc: 'Parses the prompt, builds a task graph',   color: '#8b5cf6' },
  { id: 'data',     label: 'Data Profiler', icon: '⬡', desc: 'Profiles the dataset, detects anomalies',  color: '#2dd4bf' },
  { id: 'model',    label: 'Model Search',  icon: '⟁', desc: 'Explores the model family space',          color: '#a78bfa' },
  { id: 'verifier', label: 'Verifier',      icon: '✦', desc: 'Runs independent checks on every claim',   color: '#10b981' },
  { id: 'delivery', label: 'Pipeline',      icon: '⊕', desc: 'Packages a seeded, reproducible artifact', color: '#5eead4' },
]

// Scale factor: 1.45x (45% increase)
const SCALE = 1.45

// SVG path between consecutive nodes (horizontal chain, 5 nodes)
const NODE_X = [100, 275, 450, 625, 800].map(x => x * SCALE)
const NODE_Y = 80 * SCALE
const VBOX_W = 900 * SCALE
const VBOX_H = 160 * SCALE

const NODE_R = 16 * SCALE
const NODE_R_ACTIVE = 15 * SCALE
const GLOW_R = 22 * SCALE
const ICON_FONT_SIZE = 14 * SCALE
const STROKE_W = 2 * SCALE
const STROKE_W_ACTIVE = 2.5 * SCALE
const GLOW_STROKE_W = 1.5 * SCALE
const LABEL_FONT_SIZE = 12.5 * SCALE
const DESC_FONT_SIZE = 11 * SCALE

function buildPath(x1: number, x2: number, y: number) {
  const mx = (x1 + x2) / 2
  const curveOffset = 40 * SCALE
  return `M ${x1} ${y} C ${mx} ${y - curveOffset}, ${mx} ${y + curveOffset}, ${x2} ${y}`
}

const PATHS = NODE_X.slice(0, -1).map((x, i) => buildPath(x, NODE_X[i + 1], NODE_Y))

export function AgentPipelineDiagram() {
  const trackRef = useRef<HTMLDivElement>(null)
  const reduced = prefersReducedMotion()
  // Reduced motion: everything fully lit, no scroll tracking.
  const progress = useMotionValue(reduced ? 1 : 0)

  useEffect(() => {
    if (reduced) return
    let raf = 0
    const update = () => {
      raf = 0
      const el = trackRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      const vh = window.innerHeight
      const total = Math.max(1, rect.height - vh)
      progress.set(Math.min(1, Math.max(0, -rect.top / total)))
    }
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update)
    }
    update()
    window.addEventListener('scroll', onScroll, { passive: true, capture: true })
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll, { capture: true })
      window.removeEventListener('resize', onScroll)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [progress, reduced])

  // Map overall progress to per-agent progress [0..1]
  const agentProgress = AGENTS.map((_, i) => {
    const start = i / AGENTS.length
    const end = (i + 1) / AGENTS.length
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useTransform(progress, [start, end], [0, 1])
  })

  return (
    <div ref={trackRef} className="relative" style={{ height: '280vh' }}>
      {/* Sticky container */}
      <div className="sticky top-0 flex h-screen flex-col items-center justify-center px-6 py-16">

        {/* ── SVG connection diagram ── */}
        <svg
          viewBox={`0 0 ${VBOX_W} ${VBOX_H}`}
          className="mb-8 w-full max-w-5xl"
          style={{ overflow: 'visible' }}
          aria-hidden
        >
          {/* Connection paths */}
          {PATHS.map((d, i) => (
            <g key={i}>
              {/* Static dim track */}
              <path
                d={d}
                fill="none"
                stroke="var(--as-border)"
                strokeWidth={STROKE_W}
                strokeLinecap="round"
              />
              {/* Animated draw */}
              {!reduced && (
                <motion.path
                  d={d}
                  fill="none"
                  stroke={`url(#pg${i})`}
                  strokeWidth={STROKE_W_ACTIVE}
                  strokeLinecap="round"
                  style={{ pathLength: agentProgress[i] }}
                />
              )}
            </g>
          ))}

          {/* Gradient defs */}
          <defs>
            {PATHS.map((_, i) => (
              <linearGradient key={i} id={`pg${i}`} x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor={AGENTS[i].color} />
                <stop offset="100%" stopColor={AGENTS[i + 1].color} />
              </linearGradient>
            ))}
          </defs>

          {/* Agent nodes */}
          {AGENTS.map((agent, i) => (
            <g key={agent.id}>
              {/* Glow ring */}
              {!reduced && (
                <motion.circle
                  cx={NODE_X[i]}
                  cy={NODE_Y}
                  r={GLOW_R}
                  fill="none"
                  stroke={agent.color}
                  strokeWidth={GLOW_STROKE_W}
                  style={{
                    opacity: agentProgress[i],
                    filter: `drop-shadow(0 0 ${8 * SCALE}px ${agent.color})`,
                  }}
                />
              )}
              {/* Main node circle */}
              <circle
                cx={NODE_X[i]}
                cy={NODE_Y}
                r={NODE_R}
                fill="var(--as-bg-2)"
                stroke="var(--as-border)"
                strokeWidth={STROKE_W / 2}
              />
              {/* Active fill */}
              {!reduced ? (
                <motion.circle
                  cx={NODE_X[i]}
                  cy={NODE_Y}
                  r={NODE_R_ACTIVE}
                  style={{
                    fill: agent.color,
                    opacity: agentProgress[i],
                  }}
                />
              ) : (
                <circle cx={NODE_X[i]} cy={NODE_Y} r={NODE_R_ACTIVE} fill={agent.color} opacity={0.3} />
              )}
              {/* Icon text */}
              <text
                x={NODE_X[i]}
                y={NODE_Y + 5 * SCALE}
                textAnchor="middle"
                fontSize={ICON_FONT_SIZE}
                fill="white"
                style={{ userSelect: 'none' }}
              >
                {agent.icon}
              </text>
            </g>
          ))}
        </svg>

        {/* ── Agent labels (light up on scroll) ── */}
        <div className="grid w-full max-w-5xl grid-cols-5 gap-2 text-center">
          {AGENTS.map((agent, i) => (
            <motion.div
              key={agent.id}
              style={reduced ? {} : { opacity: agentProgress[i] }}
              className="flex flex-col items-center gap-1.5"
            >
              <span
                className="font-semibold"
                style={{ color: agent.color, fontSize: LABEL_FONT_SIZE }}
              >
                {agent.label}
              </span>
              <span
                className="hidden leading-snug sm:block"
                style={{ color: 'var(--as-text-3)', fontSize: DESC_FONT_SIZE }}
              >
                {agent.desc}
              </span>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  )
}
