/**
 * CustomCursor — dot + spring-trailing glass ring.
 * Shows contextual labels ("View", "Run", "Drag") over interactive elements.
 * Disabled on touch devices and when reduced motion is preferred.
 */
import { useEffect, useState } from 'react'
import { motion, useMotionValue, useSpring } from 'framer-motion'
import { CURSOR, getFlags, prefersReducedMotion } from '../../lib/animConfig'

type CursorLabel = '' | 'View' | 'Run' | 'Drag'

// Data attribute: data-cursor="View" on any element to show a label
// data-cursor="none" to hide the ring over that element

export function CustomCursor() {
  const flags = getFlags()
  const isTouch = typeof window !== 'undefined' &&
    window.matchMedia('(hover: none)').matches

  // Don't render on touch / low intensity / reduced motion
  if (!flags.cursor || isTouch || prefersReducedMotion()) return null

  return <CursorInner />
}

function CursorInner() {
  const dotX = useMotionValue(-100)
  const dotY = useMotionValue(-100)
  const ringRawX = useMotionValue(-100)
  const ringRawY = useMotionValue(-100)

  const ringX = useSpring(ringRawX, { stiffness: 150, damping: 18, mass: 0.5 })
  const ringY = useSpring(ringRawY, { stiffness: 150, damping: 18, mass: 0.5 })

  const [label, setLabel] = useState<CursorLabel>('')
  const [pressed, setPressed] = useState(false)
  const [hidden, setHidden] = useState(false)

  useEffect(() => {
    let raf = 0

    const onMove = (e: MouseEvent) => {
      dotX.set(e.clientX)
      dotY.set(e.clientY)
      ringRawX.set(e.clientX)
      ringRawY.set(e.clientY)

      // Detect cursor label from data attribute
      const el = document.elementFromPoint(e.clientX, e.clientY)
      const cursorAttr = el?.closest('[data-cursor]')?.getAttribute('data-cursor') ?? ''
      setLabel(cursorAttr as CursorLabel)
      setHidden(cursorAttr === 'none')
    }

    const onDown = () => setPressed(true)
    const onUp = () => setPressed(false)
    const onLeave = () => setHidden(true)
    const onEnter = () => setHidden(false)

    document.addEventListener('mousemove', onMove, { passive: true })
    document.addEventListener('mousedown', onDown)
    document.addEventListener('mouseup', onUp)
    document.documentElement.addEventListener('mouseleave', onLeave)
    document.documentElement.addEventListener('mouseenter', onEnter)

    // Hide native cursor
    document.body.style.cursor = 'none'

    return () => {
      cancelAnimationFrame(raf)
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('mouseup', onUp)
      document.documentElement.removeEventListener('mouseleave', onLeave)
      document.documentElement.removeEventListener('mouseenter', onEnter)
      document.body.style.cursor = ''
    }
  }, [dotX, dotY, ringRawX, ringRawY])

  const ringSize = label ? CURSOR.ringExpand : pressed ? CURSOR.ringSize * 0.7 : CURSOR.ringSize
  const dotSize = pressed ? CURSOR.dotSize * 0.6 : CURSOR.dotSize

  if (hidden) return null

  return (
    <>
      {/* Dot — snappy, follows mouse directly */}
      <motion.div
        aria-hidden
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          x: dotX,
          y: dotY,
          translateX: '-50%',
          translateY: '-50%',
          width: dotSize,
          height: dotSize,
          borderRadius: '50%',
          background: 'var(--as-accent)',
          pointerEvents: 'none',
          zIndex: 99999,
          mixBlendMode: 'difference',
        }}
        animate={{ width: dotSize, height: dotSize }}
        transition={{ duration: 0.1 }}
      />

      {/* Ring — spring-lags behind */}
      <motion.div
        aria-hidden
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          x: ringX,
          y: ringY,
          translateX: '-50%',
          translateY: '-50%',
          width: ringSize,
          height: ringSize,
          borderRadius: '50%',
          border: '1.5px solid var(--as-accent)',
          background: label
            ? 'color-mix(in oklch, var(--as-accent) 14%, transparent)'
            : 'transparent',
          backdropFilter: label ? 'blur(6px)' : 'none',
          WebkitBackdropFilter: label ? 'blur(6px)' : 'none',
          pointerEvents: 'none',
          zIndex: 99998,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
        animate={{ width: ringSize, height: ringSize, opacity: hidden ? 0 : 1 }}
        transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
      >
        {label && (
          <motion.span
            initial={{ opacity: 0, scale: 0.7 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.7 }}
            style={{
              fontSize: '11px',
              fontWeight: 600,
              letterSpacing: '0.08em',
              color: 'var(--as-accent-hi)',
              userSelect: 'none',
              whiteSpace: 'nowrap',
            }}
          >
            {label}
          </motion.span>
        )}
      </motion.div>
    </>
  )
}
