/**
 * SplitText — splits a headline into words/chars and animates them in
 * with a masked slide-up reveal effect using Framer Motion.
 *
 * Usage:
 *   <SplitText text="From a question to a verified ML pipeline." tag="h1" />
 */
import { useRef, useEffect } from 'react'
import { motion, useInView, useAnimation } from 'framer-motion'
import { DUR, EASE, STAGGER, prefersReducedMotion } from '../../lib/animConfig'

interface SplitTextProps {
  text: string
  /** HTML tag to render as */
  tag?: 'h1' | 'h2' | 'h3' | 'h4' | 'p' | 'span' | 'div'
  /** Split into 'words' or 'chars' */
  by?: 'words' | 'chars'
  className?: string
  style?: React.CSSProperties
  delay?: number
  /** Which words to apply the gradient accent to (1-based index array) */
  accentWords?: number[]
}

const wordVariants = {
  hidden: { y: '110%', opacity: 0 },
  visible: (i: number) => ({
    y: '0%',
    opacity: 1,
    transition: {
      duration: DUR.reveal,
      delay: i * STAGGER.tight,
      ease: EASE.out,
    },
  }),
}

export function SplitText({
  text,
  tag: Tag = 'h1',
  by = 'words',
  className = '',
  style,
  delay = 0,
  accentWords = [],
}: SplitTextProps) {
  const reduced = prefersReducedMotion()
  const ref = useRef<HTMLElement>(null)
  const inView = useInView(ref as React.RefObject<Element>, { once: true, margin: '-40px 0px' })
  const controls = useAnimation()

  useEffect(() => {
    if (inView) {
      void controls.start('visible')
    }
  }, [inView, controls])

  if (reduced) {
    const R = Tag as React.ElementType
    return <R className={className} style={style}>{text}</R>
  }

  const units = by === 'words' ? text.split(' ') : text.split('')

  return (
    <Tag
      ref={ref as React.RefObject<HTMLHeadingElement>}
      className={className}
      style={{ ...style, overflow: 'hidden' }}
      aria-label={text}
    >
      <span aria-hidden style={{ display: 'inline', lineHeight: 'inherit' }}>
        {units.map((unit, i) => (
          <span
            key={i}
            style={{ display: 'inline-block', overflow: 'hidden', verticalAlign: 'bottom' }}
          >
            <motion.span
              custom={i + delay / STAGGER.tight}
              variants={wordVariants}
              initial="hidden"
              animate={controls}
              style={{
                display: 'inline-block',
                ...(accentWords.includes(i + 1)
                  ? {
                      background: 'linear-gradient(135deg, var(--as-accent-hi) 0%, var(--as-teal-hi) 100%)',
                      WebkitBackgroundClip: 'text',
                      WebkitTextFillColor: 'transparent',
                      backgroundClip: 'text',
                    }
                  : {}),
              }}
            >
              {unit}
              {by === 'words' && i < units.length - 1 ? '\u00A0' : ''}
            </motion.span>
          </span>
        ))}
      </span>
    </Tag>
  )
}
