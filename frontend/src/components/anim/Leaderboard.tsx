/**
 * Leaderboard — mock model leaderboard where bars grow on scroll and rows
 * reorder (via layout animation) when a better model is "found".
 * Purely illustrative; echoes the multi-agent model-search loop.
 */
import { useEffect, useRef, useState } from 'react'
import { motion, useInView } from 'framer-motion'
import { DUR, EASE, STAGGER, prefersReducedMotion } from '../../lib/animConfig'

interface Entry {
  trial: string
  family: string
  recall: number
}

const BASE: Entry[] = [
  { trial: 'trial_04', family: 'logistic_reg', recall: 0.812 },
  { trial: 'trial_09', family: 'random_forest', recall: 0.856 },
  { trial: 'trial_12', family: 'grad_boost', recall: 0.871 },
  { trial: 'trial_19', family: 'grad_boost · feat+', recall: 0.889 },
]

const CHAMPION: Entry = { trial: 'trial_27', family: 'grad_boost · tuned', recall: 0.912 }

export function Leaderboard({ className = '' }: { className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref as React.RefObject<Element>, { once: true, margin: '-60px 0px' })
  const [champion, setChampion] = useState(false)
  const reduced = prefersReducedMotion()

  useEffect(() => {
    if (!inView || reduced) return
    const id = window.setTimeout(() => setChampion(true), 2400)
    return () => window.clearTimeout(id)
  }, [inView, reduced])

  const rows = (champion || reduced ? [...BASE, ...(reduced ? [CHAMPION] : champion ? [CHAMPION] : [])] : BASE)
    .slice()
    .sort((a, b) => b.recall - a.recall)
  const best = rows[0]?.recall ?? 1

  return (
    <div ref={ref} className={className}>
      <ul className="space-y-3">
        {rows.map((row, i) => {
          const isBest = i === 0
          return (
            <motion.li
              key={row.trial}
              layout={!reduced}
              initial={reduced ? false : { opacity: 0, x: -14 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: DUR.normal, delay: reduced ? 0 : i * STAGGER.normal, ease: EASE.out }}
              className="rounded-2xl border px-4 py-3"
              style={{
                borderColor: isBest
                  ? 'color-mix(in oklch, var(--as-verify) 40%, transparent)'
                  : 'var(--as-border)',
                background: isBest
                  ? 'color-mix(in oklch, var(--as-verify) 7%, transparent)'
                  : 'color-mix(in oklch, var(--as-accent) 3%, transparent)',
                boxShadow: isBest ? '0 0 24px rgba(16,185,129,0.18)' : 'none',
              }}
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="mono text-[12px]" style={{ color: 'var(--as-text-2)' }}>
                  {row.trial} <span style={{ color: 'var(--as-text-3)' }}>· {row.family}</span>
                </span>
                <span
                  className="mono tnum text-[13px] font-semibold"
                  style={{ color: isBest ? 'var(--as-verify)' : 'var(--as-teal-hi)' }}
                >
                  {row.recall.toFixed(3)}
                </span>
              </div>
              <div
                className="mt-2 h-[6px] overflow-hidden rounded-full"
                style={{ background: 'var(--as-border)' }}
              >
                <motion.div
                  className="h-full rounded-full"
                  style={{
                    transformOrigin: 'left',
                    background: isBest
                      ? 'linear-gradient(90deg, var(--as-verify), var(--as-teal-hi))'
                      : 'linear-gradient(90deg, var(--as-accent), var(--as-teal))',
                    boxShadow: isBest ? '0 0 10px rgba(16,185,129,0.5)' : 'none',
                  }}
                  initial={reduced ? false : { scaleX: 0 }}
                  animate={{ scaleX: row.recall / best }}
                  transition={{ duration: 0.9, delay: reduced ? 0 : 0.15 + i * STAGGER.normal, ease: EASE.out }}
                />
              </div>
            </motion.li>
          )
        })}
      </ul>
      <div className="mono mt-4 text-[11.5px]" style={{ color: 'var(--as-text-3)' }}>
        {champion ? '✦ new best · trial_27 promoted' : 'searching model space…'}
      </div>
    </div>
  )
}
