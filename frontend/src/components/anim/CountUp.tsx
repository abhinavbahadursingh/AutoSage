/**
 * CountUp — animates a number from 0 to `to` when it scrolls into view.
 * Respects reduced motion (shows final value immediately).
 */
import { useRef, useEffect, useState } from 'react'
import { useInView } from 'framer-motion'
import { prefersReducedMotion } from '../../lib/animConfig'

interface CountUpProps {
  to: number
  duration?: number
  decimals?: number
  prefix?: string
  suffix?: string
  className?: string
}

function easeOutCubic(t: number) {
  return 1 - Math.pow(1 - t, 3)
}

export function CountUp({
  to,
  duration = 1.8,
  decimals = 0,
  prefix = '',
  suffix = '',
  className = '',
}: CountUpProps) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref as React.RefObject<Element>, { once: true, margin: '-60px 0px' })
  const [value, setValue] = useState(0)
  const started = useRef(false)

  useEffect(() => {
    if (!inView || started.current) return
    if (prefersReducedMotion()) {
      setValue(to)
      return
    }
    started.current = true
    const start = performance.now()
    const ms = duration * 1000

    const tick = (now: number) => {
      const elapsed = now - start
      const progress = Math.min(elapsed / ms, 1)
      setValue(to * easeOutCubic(progress))
      if (progress < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  }, [inView, to, duration])

  return (
    <span ref={ref} className={className}>
      {prefix}{value.toFixed(decimals)}{suffix}
    </span>
  )
}
