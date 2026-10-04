/**
 * useScrollReveal / RevealBlock
 * ──────────────────────────────
 * Fade + translate-up + blur-to-sharp reveal triggered by IntersectionObserver.
 * Use <RevealBlock> as a wrapper or useScrollReveal() for custom elements.
 *
 * <RevealBlock delay={0.1} stagger>
 *   <p>child 1</p>
 *   <p>child 2</p>  ← gets extra delay
 * </RevealBlock>
 */
import {
  useRef,
  useEffect,
  type ReactNode,
  type CSSProperties,
} from 'react'
import { motion, useInView, useAnimation } from 'framer-motion'
import { DUR, EASE, REVEAL, STAGGER, prefersReducedMotion } from '../../lib/animConfig'

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useScrollReveal(options?: { once?: boolean }) {
  const ref = useRef<HTMLElement>(null)
  // NOTE: framer-motion's MarginType only accepts statically-analyzable strings,
  // so the trigger margin is fixed (matches REVEAL.threshold ≈ 15% of viewport).
  const inView = useInView(ref, { once: options?.once ?? true, margin: '-15px 0px' })
  return { ref, inView }
}

// ── Framer Motion variants ───────────────────────────────────────────────────

const hidden = {
  opacity: 0,
  y: REVEAL.yOffset,
  filter: `blur(${REVEAL.blur})`,
}

const visible = {
  opacity: 1,
  y: 0,
  filter: 'blur(0px)',
}

const containerVariants = (stagger: number) => ({
  hidden: {},
  visible: {
    transition: {
      staggerChildren: stagger,
    },
  },
})

const childVariants = {
  hidden,
  visible: {
    ...visible,
    transition: {
      duration: DUR.reveal,
      ease: EASE.out,
    },
  },
}

const selfVariant = (delay = 0) => ({
  hidden,
  visible: {
    ...visible,
    transition: {
      duration: DUR.reveal,
      delay,
      ease: EASE.out,
    },
  },
})

// ── Component ────────────────────────────────────────────────────────────────

interface RevealBlockProps {
  children: ReactNode
  /** Extra delay before this block starts (seconds) */
  delay?: number
  /** If true, children stagger sequentially */
  stagger?: boolean | 'tight' | 'loose'
  className?: string
  style?: CSSProperties
  /** Intrinsic element to render as (avoids the removed global JSX namespace) */
  as?: 'div' | 'section' | 'span' | 'li' | 'ul' | 'p' | 'h1' | 'h2' | 'h3'
}

export function RevealBlock({
  children,
  delay = 0,
  stagger = false,
  className,
  style,
  as = 'div',
}: RevealBlockProps) {
  const reduced = prefersReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref as React.RefObject<Element>, {
    once: true,
    margin: '-15px 0px',
  })
  const controls = useAnimation()

  useEffect(() => {
    if (inView) void controls.start('visible')
  }, [inView, controls])

  if (reduced) {
    // Reduced motion: just render children, no animation
    const Tag = as as React.ElementType
    return <Tag className={className} style={style}>{children}</Tag>
  }

  if (stagger) {
    const staggerTime =
      stagger === 'tight'
        ? STAGGER.tight
        : stagger === 'loose'
          ? STAGGER.loose
          : STAGGER.normal

    return (
      <motion.div
        ref={ref}
        className={className}
        style={style}
        initial="hidden"
        animate={controls}
        variants={containerVariants(staggerTime)}
      >
        {/* Wrap each direct child in the child variant */}
        {Array.isArray(children)
          ? children.map((child, i) => (
              <motion.div key={i} variants={childVariants}>
                {child}
              </motion.div>
            ))
          : <motion.div variants={childVariants}>{children}</motion.div>}
      </motion.div>
    )
  }

  // Single block reveal
  const MotionTag =
    (motion[as as keyof typeof motion] as typeof motion.div | undefined) ?? motion.div
  return (
    <MotionTag
      ref={ref as React.RefObject<HTMLDivElement>}
      className={className}
      style={style}
      initial="hidden"
      animate={controls}
      variants={selfVariant(delay)}
    >
      {children}
    </MotionTag>
  )
}

// ── Staggered list reveal (each li/item fades up) ───────────────────────────

export function RevealList({
  items,
  render,
  className,
  stagger = STAGGER.normal,
}: {
  items: unknown[]
  render: (item: unknown, index: number) => ReactNode
  className?: string
  stagger?: number
}) {
  const reduced = prefersReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref as React.RefObject<Element>, { once: true, margin: '-60px 0px' })
  const controls = useAnimation()

  useEffect(() => {
    if (inView) void controls.start('visible')
  }, [inView, controls])

  if (reduced) {
    return <div className={className}>{items.map((item, i) => render(item, i))}</div>
  }

  return (
    <motion.div
      ref={ref}
      className={className}
      initial="hidden"
      animate={controls}
      variants={{ hidden: {}, visible: { transition: { staggerChildren: stagger } } }}
    >
      {items.map((item, i) => (
        <motion.div key={i} variants={childVariants}>
          {render(item, i)}
        </motion.div>
      ))}
    </motion.div>
  )
}
