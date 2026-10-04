/**
 * TypewriterText — true typing animation: characters appear one by one with
 * a blinking block caret, the word holds, deletes fast, then the next word
 * types. Used in the hero headline for
 * "verified" → "reproducible" → "auditable" → "explainable".
 */
import { useState, useEffect } from 'react'
import { prefersReducedMotion } from '../../lib/animConfig'

interface TypewriterTextProps {
  words: string[]
  /** ms to hold a fully-typed word before deleting */
  interval?: number
  /** ms per keystroke while typing (plus a little human jitter) */
  typeSpeed?: number
  /** ms per keystroke while deleting */
  deleteSpeed?: number
  className?: string
  style?: React.CSSProperties
}

export function TypewriterText({
  words,
  interval = 2000,
  typeSpeed = 65,
  deleteSpeed = 30,
  className = '',
  style,
}: TypewriterTextProps) {
  const [index, setIndex] = useState(0)
  const [chars, setChars] = useState(0)
  const [deleting, setDeleting] = useState(false)
  const reduced = prefersReducedMotion()

  useEffect(() => {
    if (reduced || words.length === 0) return
    const word = words[index] ?? ''
    let delay: number
    if (!deleting && chars < word.length) {
      delay = typeSpeed + Math.random() * 45 // human jitter
    } else if (!deleting) {
      delay = interval // hold the completed word
    } else if (chars > 0) {
      delay = deleteSpeed
    } else {
      delay = 350 // brief pause on empty before the next word
    }
    const id = window.setTimeout(() => {
      if (!deleting && chars < word.length) {
        setChars((c) => c + 1)
      } else if (!deleting) {
        setDeleting(true)
      } else if (chars > 0) {
        setChars((c) => c - 1)
      } else {
        setDeleting(false)
        setIndex((i) => (i + 1) % words.length)
      }
    }, delay)
    return () => window.clearTimeout(id)
  }, [chars, deleting, index, words, interval, typeSpeed, deleteSpeed, reduced])

  if (reduced || words.length === 0) {
    return (
      <span className={className} style={style}>
        {words[0] ?? ''}
      </span>
    )
  }

  const word = words[index] ?? ''
  // Reserve the longest word's width so typing doesn't reflow the headline.
  const maxLen = Math.max(...words.map((w) => w.length))

  return (
    <span
      className={className}
      style={{
        display: 'inline-block',
        minWidth: `${maxLen}ch`,
        verticalAlign: 'bottom',
        ...style,
      }}
      aria-label={word}
    >
      <span aria-hidden="true">
        {word.slice(0, chars)}
        <span className="typewriter-caret" aria-hidden="true" />
      </span>
    </span>
  )
}
