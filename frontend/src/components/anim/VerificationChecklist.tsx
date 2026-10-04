/**
 * VerificationChecklist — items tick off sequentially with SVG path
 * check-draw animation, then a "Verified" glow badge appears.
 */
import { useRef } from 'react'
import { motion, useInView } from 'framer-motion'
import { DUR, EASE, STAGGER, prefersReducedMotion } from '../../lib/animConfig'

const ITEMS = [
  'Leakage checks passed',
  'Metric sanity verified',
  'Baseline model dominated',
  'AST security analysis clean',
  'Reproducibility seed locked',
]

// SVG checkmark path for a 20×20 viewBox
const CHECK_PATH = 'M 4 10 L 8 14 L 16 6'

function CheckItem({ label, index }: { label: string; index: number }) {
  const reduced = prefersReducedMotion()
  const delay = index * STAGGER.loose

  return (
    <motion.li
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: DUR.normal, delay, ease: EASE.out }}
      className="flex items-center gap-3 py-2"
      style={{ borderBottom: '1px solid var(--as-border)' }}
    >
      {/* Check circle */}
      <motion.div
        initial={{ scale: 0.5, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: DUR.fast, delay: delay + 0.1, ease: EASE.snap }}
        className="shrink-0 flex items-center justify-center rounded-full border"
        style={{
          width: 22,
          height: 22,
          background: 'color-mix(in oklch, var(--as-verify) 12%, transparent)',
          borderColor: 'color-mix(in oklch, var(--as-verify) 40%, transparent)',
          boxShadow: '0 0 8px rgba(16,185,129,0.2)',
        }}
      >
        <svg viewBox="0 0 20 20" width="12" height="12" fill="none">
          {reduced ? (
            <path d={CHECK_PATH} stroke="var(--as-verify)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          ) : (
            <motion.path
              d={CHECK_PATH}
              stroke="var(--as-verify)"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.4, delay: delay + 0.25, ease: EASE.out }}
            />
          )}
        </svg>
      </motion.div>
      <span className="text-[14.5px]" style={{ color: 'var(--as-text-2)' }}>
        {label}
      </span>
    </motion.li>
  )
}

export function VerificationChecklist({ className = '' }: { className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref as React.RefObject<Element>, { once: true, margin: '-60px 0px' })

  return (
    <div ref={ref} className={className}>
      {inView && (
        <>
          <ul className="mb-5">
            {ITEMS.map((item, i) => (
              <CheckItem key={item} label={item} index={i} />
            ))}
          </ul>

          {/* Verified badge */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{
              duration: DUR.normal,
              delay: ITEMS.length * STAGGER.loose + 0.3,
              ease: EASE.snap,
            }}
            className="inline-flex items-center gap-2 rounded-full border px-4 py-2"
            style={{
              background: 'color-mix(in oklch, var(--as-verify) 10%, transparent)',
              borderColor: 'color-mix(in oklch, var(--as-verify) 35%, transparent)',
              boxShadow: '0 0 24px rgba(16,185,129,0.25)',
            }}
          >
            <motion.span
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ repeat: Infinity, repeatDelay: 2, duration: 0.4 }}
              style={{ color: 'var(--as-verify)', fontSize: 14 }}
            >
              ✦
            </motion.span>
            <span
              className="text-[13px] font-semibold tracking-wide"
              style={{ color: 'var(--as-verify)' }}
            >
              VERIFIED
            </span>
          </motion.div>
        </>
      )}
    </div>
  )
}
