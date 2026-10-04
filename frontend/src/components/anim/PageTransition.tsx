/**
 * PageTransition — wraps a route page with fade + slight slide.
 */
import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { DUR, EASE, getFlags, prefersReducedMotion } from '../../lib/animConfig'

const variants = {
  initial:  { opacity: 0, y: 10, filter: 'blur(4px)' },
  animate:  { opacity: 1, y: 0,  filter: 'blur(0px)' },
  exit:     { opacity: 0, y: -6, filter: 'blur(2px)' },
}

export function PageTransition({ children }: { children: ReactNode }) {
  const flags = getFlags()
  if (!flags.pageTransitions || prefersReducedMotion()) return <>{children}</>
  return (
    <motion.div
      variants={variants}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={{ duration: DUR.normal, ease: EASE.out }}
      style={{ height: '100%', width: '100%' }}
    >
      {children}
    </motion.div>
  )
}
