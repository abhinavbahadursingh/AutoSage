/**
 * TerminalPanel — animated streaming log lines with a blinking caret.
 * Lines drip in one-by-one, cycling on repeat to look live.
 */
import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence, useInView } from 'framer-motion'
import { DUR, EASE, prefersReducedMotion } from '../../lib/animConfig'

const LOG_LINES = [
  { level: 'INFO',     agent: 'Orchestrator', text: 'experiment created · CREATED' },
  { level: 'INFO',     agent: 'System',       text: 'start accepted · status=QUEUED' },
  { level: 'INFO',     agent: 'Planner',      text: 'stage started · discovery' },
  { level: 'INFO',     agent: 'DataProfiler', text: 'profiling 12,847 rows × 41 cols' },
  { level: 'INFO',     agent: 'DataProfiler', text: 'stage completed · profiling' },
  { level: 'INFO',     agent: 'Preprocessor', text: 'stage started · preprocessing' },
  { level: 'DECISION', agent: 'Preprocessor', text: 'strategy=standardize · skew_features=7' },
  { level: 'INFO',     agent: 'ModelSearch',  text: 'exploring family=gradient_boosting' },
  { level: 'METRIC',   agent: 'Evaluator',    text: 'trial_12 · recall=0.871 · roc_auc=0.934' },
  { level: 'METRIC',   agent: 'Evaluator',    text: 'trial_19 · recall=0.889 · roc_auc=0.941' },
  { level: 'INFO',     agent: 'Verifier',     text: 'verification attempt 1/3' },
  { level: 'VERIFY',   agent: 'Verifier',     text: 'verification passed · gate=STRICT' },
  { level: 'VERIFY',   agent: 'Orchestrator', text: 'experiment completed ✦' },
]

const LEVEL_COLOR: Record<string, string> = {
  INFO:     'var(--as-text-3)',
  DECISION: 'var(--as-accent-hi)',
  METRIC:   'var(--as-teal-hi)',
  VERIFY:   'var(--as-verify)',
  WARN:     'var(--as-warn)',
}

const AGENT_COLOR: Record<string, string> = {
  Orchestrator: 'var(--as-accent)',
  System:       'var(--as-text-3)',
  Planner:      '#c084fc',
  DataProfiler: 'var(--as-teal)',
  Preprocessor: '#60a5fa',
  ModelSearch:  '#f472b6',
  Evaluator:    'var(--as-teal-hi)',
  Verifier:     'var(--as-verify)',
}

export function TerminalPanel({ className = '' }: { className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref as React.RefObject<Element>, { once: false, margin: '-80px 0px' })
  const [visibleCount, setVisibleCount] = useState(0)
  const timerRef = useRef<number | null>(null)
  const reduced = prefersReducedMotion()

  useEffect(() => {
    if (!inView) return
    if (reduced) {
      setVisibleCount(LOG_LINES.length)
      return
    }
    setVisibleCount(0)
    let i = 0
    const drip = () => {
      i++
      setVisibleCount(Math.min(i, LOG_LINES.length))
      if (i < LOG_LINES.length) {
        timerRef.current = window.setTimeout(drip, 340 + Math.random() * 220)
      } else {
        // After pause, restart
        timerRef.current = window.setTimeout(() => {
          setVisibleCount(0)
          i = 0
          timerRef.current = window.setTimeout(drip, 600)
        }, 3500)
      }
    }
    timerRef.current = window.setTimeout(drip, 300)
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [inView, reduced])

  const lines = LOG_LINES.slice(0, visibleCount)

  return (
    <div
      ref={ref}
      className={`glass grain rounded-2xl overflow-hidden ${className}`}
      style={{ fontFamily: 'var(--font-mono)', boxShadow: 'var(--as-glass-shadow)' }}
    >
      {/* Title bar */}
      <div
        className="flex items-center gap-2 border-b px-4 py-2.5"
        style={{ borderColor: 'var(--as-border)', background: 'color-mix(in oklch, var(--as-accent) 5%, transparent)' }}
      >
        <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#ef4444' }} />
        <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#f59e0b' }} />
        <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#10b981' }} />
        <span className="ml-3 text-[12px]" style={{ color: 'var(--as-text-3)' }}>
          autosage · experiment runner
        </span>
      </div>

      {/* Log output */}
      <div className="px-4 py-3 space-y-0.5 min-h-[200px]">
        <AnimatePresence initial={false}>
          {lines.map((line, i) => (
            <motion.div
              key={`${i}-${line.text}`}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: DUR.fast, ease: EASE.out }}
              className="flex items-baseline gap-2 text-[12px]"
            >
              <span style={{ color: LEVEL_COLOR[line.level] ?? 'var(--as-text-3)', minWidth: 54 }}>
                {line.level}
              </span>
              <span style={{ color: AGENT_COLOR[line.agent] ?? 'var(--as-text-2)', minWidth: 90 }}>
                {line.agent}
              </span>
              <span style={{ color: 'var(--as-text-2)' }}>{line.text}</span>
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Blinking caret */}
        {visibleCount < LOG_LINES.length && (
          <motion.span
            animate={{ opacity: [1, 0, 1] }}
            transition={{ repeat: Infinity, duration: 0.9 }}
            className="inline-block w-[7px] h-[13px] align-middle rounded-sm ml-1"
            style={{ background: 'var(--as-accent)' }}
          />
        )}
      </div>
    </div>
  )
}
