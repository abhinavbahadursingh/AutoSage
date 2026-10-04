/**
 * SectionNav — in-page links with a sliding glass indicator pill.
 * Active section is tracked with IntersectionObserver (viewport-based,
 * so it works with window scroll AND inner overflow scroll containers).
 */
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { DUR, EASE } from '../../lib/animConfig'

const LINKS = [
  { id: 'pipeline', label: 'Pipeline' },
  { id: 'how', label: 'How it works' },
  { id: 'demo', label: 'Live demo' },
  { id: 'start', label: 'Start' },
]

export function SectionNav() {
  const [active, setActive] = useState<string>('')

  useEffect(() => {
    const sections = LINKS
      .map((l) => document.getElementById(l.id))
      .filter((el): el is HTMLElement => el !== null)
    if (sections.length === 0) return

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActive(entry.target.id)
        }
      },
      { rootMargin: '-40% 0px -55% 0px', threshold: 0 },
    )
    sections.forEach((s) => io.observe(s))
    return () => io.disconnect()
  }, [])

  const go = (id: string) => {
    setActive(id)
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <nav aria-label="Page sections" className="hidden items-center gap-1 lg:flex">
      {LINKS.map((l) => {
        const isActive = active === l.id
        return (
          <button
            key={l.id}
            onClick={() => go(l.id)}
            className="relative rounded-full px-3.5 py-1.5 text-[13.5px] font-medium transition-colors"
            style={{ color: isActive ? 'var(--as-text)' : 'var(--as-text-3)' }}
            aria-current={isActive ? 'true' : undefined}
            data-cursor="View"
          >
            {isActive && (
              <motion.span
                layoutId="section-nav-pill"
                transition={{ duration: DUR.fast, ease: EASE.out }}
                className="absolute inset-0 rounded-full border"
                style={{
                  background: 'color-mix(in oklch, var(--as-accent) 12%, transparent)',
                  borderColor: 'var(--as-border-hi)',
                  boxShadow: '0 0 16px var(--as-accent-glow)',
                }}
              />
            )}
            <span className="relative">{l.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
