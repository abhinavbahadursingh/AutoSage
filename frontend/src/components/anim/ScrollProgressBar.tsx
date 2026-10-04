/**
 * ScrollProgressBar — glowing gradient line fixed at top of viewport.
 *
 * Container-aware: app pages scroll inside their own overflow containers
 * rather than the window, so we listen with capture:true and measure
 * whichever element actually scrolled (falling back to window scroll).
 */
import { useEffect } from 'react'
import { useMotionValue, useSpring, motion } from 'framer-motion'

export function ScrollProgressBar() {
  const progress = useMotionValue(0)
  const scaleX = useSpring(progress, {
    stiffness: 200,
    damping: 30,
    restDelta: 0.001,
  })

  useEffect(() => {
    const onScroll = (e: Event) => {
      const t = e.target as Document | Element | null
      let p = 0
      if (t instanceof Element) {
        const max = t.scrollHeight - t.clientHeight
        p = max > 0 ? t.scrollTop / max : progress.get()
      } else {
        const max = document.documentElement.scrollHeight - window.innerHeight
        p = max > 0 ? window.scrollY / max : 0
      }
      progress.set(Math.min(1, Math.max(0, p)))
    }
    // capture:true catches scroll events from inner overflow containers
    // (scroll events don't bubble, but the capture phase reaches window)
    window.addEventListener('scroll', onScroll, { passive: true, capture: true })
    return () => window.removeEventListener('scroll', onScroll, { capture: true })
  }, [progress])

  return (
    <motion.div
      aria-hidden
      style={{
        scaleX,
        transformOrigin: '0%',
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: '2px',
        zIndex: 9999,
        background: 'linear-gradient(90deg, var(--as-accent), var(--as-teal), var(--as-accent-hi))',
        boxShadow: '0 0 12px var(--as-accent-glow), 0 0 24px var(--as-teal-glow)',
        pointerEvents: 'none',
      }}
    />
  )
}
