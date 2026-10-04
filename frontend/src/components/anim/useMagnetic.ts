/**
 * useMagnetic — pulls an element slightly toward the cursor when hovered.
 * Attach the returned ref and motion values to a motion element.
 *
 * Usage:
 *   const { ref, x, y } = useMagnetic()
 *   <motion.button ref={ref} style={{ x, y }}>Click</motion.button>
 */
import { useRef } from 'react'
import { useMotionValue, useSpring } from 'framer-motion'
import { prefersReducedMotion, INTENSITY } from '../../lib/animConfig'

export function useMagnetic(strength = 0.35) {
  const ref = useRef<HTMLElement>(null)
  const rawX = useMotionValue(0)
  const rawY = useMotionValue(0)
  const x = useSpring(rawX, { stiffness: 200, damping: 20 })
  const y = useSpring(rawY, { stiffness: 200, damping: 20 })

  const onMouseMove = (e: React.MouseEvent) => {
    if (prefersReducedMotion() || INTENSITY === 'low') return
    const el = ref.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const cx = rect.left + rect.width / 2
    const cy = rect.top + rect.height / 2
    rawX.set((e.clientX - cx) * strength)
    rawY.set((e.clientY - cy) * strength)
  }

  const onMouseLeave = () => {
    rawX.set(0)
    rawY.set(0)
  }

  return { ref, x, y, onMouseMove, onMouseLeave }
}
