/**
 * MetricChart — animated accuracy / loss curves that draw on scroll.
 * SVG stroke draw (pathLength) + pulsing end-dots; transform/opacity only.
 */
import { useRef } from 'react'
import { motion, useInView } from 'framer-motion'
import { DUR, EASE, prefersReducedMotion } from '../../lib/animConfig'

const ACC_PATH = 'M 10 158 C 62 150, 92 132, 132 118 S 222 72, 310 36'
const LOSS_PATH = 'M 10 32 C 62 40, 102 68, 152 90 S 252 138, 310 148'

export function MetricChart({ className = '' }: { className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref as React.RefObject<Element>, { once: true, margin: '-60px 0px' })
  const reduced = prefersReducedMotion()
  const animate = inView || reduced

  return (
    <div ref={ref} className={className}>
      {/* Legend */}
      <div className="mb-3 flex items-center gap-5">
        <span className="flex items-center gap-2 text-[12.5px]" style={{ color: 'var(--as-text-2)' }}>
          <span className="h-[3px] w-5 rounded-full" style={{ background: 'var(--as-teal-hi)' }} />
          recall <span className="mono tnum font-semibold" style={{ color: 'var(--as-teal-hi)' }}>0.912</span>
        </span>
        <span className="flex items-center gap-2 text-[12.5px]" style={{ color: 'var(--as-text-2)' }}>
          <span className="h-[3px] w-5 rounded-full" style={{ background: 'var(--as-accent-hi)' }} />
          loss <span className="mono tnum font-semibold" style={{ color: 'var(--as-accent-hi)' }}>0.214</span>
        </span>
      </div>

      <svg viewBox="0 0 320 180" className="w-full" role="img" aria-label="Recall rising and loss falling over trials">
        {/* Grid */}
        {[40, 75, 110, 145].map((y) => (
          <line key={y} x1="10" x2="310" y1={y} y2={y} stroke="var(--as-border)" strokeWidth="1" strokeDasharray="3 5" />
        ))}

        {/* Loss curve */}
        {reduced ? (
          <path d={LOSS_PATH} fill="none" stroke="var(--as-accent-hi)" strokeWidth="2" strokeLinecap="round" />
        ) : (
          <motion.path
            d={LOSS_PATH}
            fill="none"
            stroke="var(--as-accent-hi)"
            strokeWidth="2"
            strokeLinecap="round"
            initial={{ pathLength: 0 }}
            animate={animate ? { pathLength: 1 } : {}}
            transition={{ duration: 1.6, delay: 0.2, ease: EASE.out }}
          />
        )}

        {/* Accuracy curve */}
        {reduced ? (
          <path d={ACC_PATH} fill="none" stroke="var(--as-teal-hi)" strokeWidth="2.5" strokeLinecap="round" />
        ) : (
          <motion.path
            d={ACC_PATH}
            fill="none"
            stroke="var(--as-teal-hi)"
            strokeWidth="2.5"
            strokeLinecap="round"
            style={{ filter: 'drop-shadow(0 0 6px var(--as-teal-glow))' }}
            initial={{ pathLength: 0 }}
            animate={animate ? { pathLength: 1 } : {}}
            transition={{ duration: 1.8, ease: EASE.out }}
          />
        )}

        {/* End dots */}
        {animate && (
          <>
            <motion.circle
              cx="310" cy="36" r="4"
              fill="var(--as-teal-hi)"
              initial={reduced ? false : { scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: DUR.fast, delay: 1.7, ease: EASE.snap }}
            />
            <motion.circle
              cx="310" cy="148" r="3.5"
              fill="var(--as-accent-hi)"
              initial={reduced ? false : { scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: DUR.fast, delay: 1.6, ease: EASE.snap }}
            />
          </>
        )}
      </svg>

      <div className="mono mt-2 flex justify-between text-[11px]" style={{ color: 'var(--as-text-3)' }}>
        <span>trial_01</span>
        <span>27 trials · 5-fold CV</span>
        <span>trial_27</span>
      </div>
    </div>
  )
}
