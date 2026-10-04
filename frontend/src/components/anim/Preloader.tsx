/**
 * Preloader — intro overlay shown once per session.
 * Logo strokes draw in, then the curtain slides up to reveal the app.
 * Skipped entirely on reduced motion or repeat visits in the same session.
 */
import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { DUR, EASE, prefersReducedMotion } from '../../lib/animConfig'

const SEEN_KEY = 'as-preloader-seen'

export function Preloader() {
  const [show, setShow] = useState(() => {
    if (typeof window === 'undefined') return false
    if (prefersReducedMotion()) return false
    try {
      return window.sessionStorage.getItem(SEEN_KEY) !== '1'
    } catch {
      return true
    }
  })

  useEffect(() => {
    if (!show) return
    let done = false
    const finish = () => {
      if (done) return
      done = true
      try {
        window.sessionStorage.setItem(SEEN_KEY, '1')
      } catch {
        /* ignore */
      }
      // Let the logo-draw finish (min display) before lifting the curtain
      window.setTimeout(() => setShow(false), 1250)
    }
    if (document.readyState === 'complete') {
      window.setTimeout(finish, 350)
    } else {
      window.addEventListener('load', finish, { once: true })
    }
    // Safety cap so content is never blocked
    const cap = window.setTimeout(finish, 2400)
    return () => {
      window.removeEventListener('load', finish)
      window.clearTimeout(cap)
    }
  }, [show])

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          aria-hidden
          exit={{ y: '-100%' }}
          transition={{ duration: 0.7, ease: EASE.out }}
          className="fixed inset-0 z-[10000] flex items-center justify-center"
          style={{ background: 'var(--as-bg)' }}
        >
          <motion.div
            exit={{ opacity: 0, y: -16 }}
            transition={{ duration: 0.3, ease: EASE.in }}
            className="flex flex-col items-center gap-5"
          >
            {/* Logo mark — strokes draw in */}
            <svg width="54" height="54" viewBox="0 0 32 32" fill="none">
              <motion.rect
                x="1" y="1" width="30" height="30" rx="6"
                stroke="var(--as-border-hi)"
                strokeWidth="1.5"
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ duration: 0.7, ease: EASE.out }}
              />
              <motion.path
                d="M8 22 L16 8 L24 22"
                stroke="var(--as-accent-hi)"
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.6, delay: 0.25, ease: EASE.out }}
              />
              <motion.path
                d="M11.5 17.5 H20.5"
                stroke="var(--as-teal-hi)"
                strokeWidth="2.4"
                strokeLinecap="round"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.4, delay: 0.6, ease: EASE.out }}
              />
              <motion.circle
                cx="16" cy="25" r="1.5"
                fill="var(--as-accent)"
                initial={{ opacity: 0, scale: 0 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3, delay: 0.85 }}
              />
            </svg>

            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: DUR.normal, delay: 0.5, ease: EASE.out }}
              className="text-[17px] font-semibold tracking-tight"
              style={{ color: 'var(--as-text)' }}
            >
              AutoSage
            </motion.div>

            {/* Thin loading shimmer */}
            <div
              className="relative h-[2px] w-40 overflow-hidden rounded-full"
              style={{ background: 'var(--as-border)' }}
            >
              <div
                className="absolute inset-y-0 w-1/3 rounded-full"
                style={{
                  background: 'linear-gradient(90deg, var(--as-accent), var(--as-teal))',
                  boxShadow: '0 0 12px var(--as-accent-glow)',
                  animation: 'indeterminate 1.1s ease-in-out infinite',
                }}
              />
            </div>

            <div
              className="mono text-[11px] tracking-[0.18em] uppercase"
              style={{ color: 'var(--as-text-3)' }}
            >
              Verified Multi-Agent AutoML
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
