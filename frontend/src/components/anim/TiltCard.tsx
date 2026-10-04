/**
 * TiltCard — wraps children with a 3D tilt effect on mouse move.
 * Max ~8°, with a specular glow highlight that follows the cursor.
 * Falls back to no tilt on touch devices and reduced motion.
 */
import { useRef, type ReactNode, type CSSProperties } from 'react'
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion'
import { TILT, DUR, prefersReducedMotion } from '../../lib/animConfig'

interface TiltCardProps {
  children: ReactNode
  className?: string
  style?: CSSProperties
  glowColor?: string
  maxDeg?: number
}

export function TiltCard({
  children,
  className = '',
  style,
  glowColor = 'var(--as-accent-glow)',
  maxDeg = TILT.maxDeg,
}: TiltCardProps) {
  const ref = useRef<HTMLDivElement>(null)
  const reduced = prefersReducedMotion()

  // Raw mouse position within the card [-0.5, 0.5]
  const rawX = useMotionValue(0)
  const rawY = useMotionValue(0)
  const glowX = useMotionValue(50)
  const glowY = useMotionValue(50)

  // Spring-smooth the tilt
  const springConfig = { stiffness: 300, damping: 30, mass: 0.5 }
  const x = useSpring(rawX, springConfig)
  const y = useSpring(rawY, springConfig)

  const rotateY = useTransform(x, [-0.5, 0.5], [-maxDeg, maxDeg])
  const rotateX = useTransform(y, [-0.5, 0.5], [maxDeg, -maxDeg])

  const handleMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (reduced || !ref.current) return
    const rect = ref.current.getBoundingClientRect()
    const nx = (e.clientX - rect.left) / rect.width - 0.5
    const ny = (e.clientY - rect.top) / rect.height - 0.5
    rawX.set(nx)
    rawY.set(ny)
    // glow follows cursor (percentage for bg-position)
    glowX.set(((e.clientX - rect.left) / rect.width) * 100)
    glowY.set(((e.clientY - rect.top) / rect.height) * 100)
  }

  const handleLeave = () => {
    rawX.set(0)
    rawY.set(0)
    glowX.set(50)
    glowY.set(50)
  }

  if (reduced) {
    return (
      <div className={className} style={style}>
        {children}
      </div>
    )
  }

  return (
    <motion.div
      ref={ref}
      className={className}
      style={{
        ...style,
        rotateX,
        rotateY,
        transformStyle: 'preserve-3d',
        transformPerspective: 800,
        willChange: 'transform',
        position: 'relative',
        transition: `box-shadow ${DUR.fast}s ease`,
      }}
      whileHover={{ scale: TILT.scalePeak }}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
    >
      {children}

      {/* Specular glow overlay — follows cursor within the card */}
      <motion.div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          borderRadius: 'inherit',
          pointerEvents: 'none',
          background: `radial-gradient(200px circle at ${glowX.get()}% ${glowY.get()}%, ${glowColor}, transparent 70%)`,
          opacity: 0.5,
          mixBlendMode: 'screen',
        }}
      />
    </motion.div>
  )
}
