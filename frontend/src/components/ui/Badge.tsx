import type { ReactNode } from 'react'
import type { Tone } from '../../lib/tones'

const TONES: Record<Tone, string> = {
  neutral: 'border-ink-500 text-paper-200 bg-ink-750',
  accent: 'border-accent-600/60 text-accent-300 bg-accent-900/60',
  verify: 'border-verify-500/40 text-verify-500 bg-verify-900/60',
  warn: 'border-warn-500/40 text-warn-500 bg-warn-900/60',
  conflict: 'border-conflict-500/40 text-conflict-500 bg-conflict-900/60',
  dim: 'border-ink-600 text-paper-400 bg-transparent',
}

export function Badge({
  children,
  tone = 'neutral',
  className = '',
}: {
  children: ReactNode
  tone?: Tone
  className?: string
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-sm border px-1.5 py-[1px] text-[12.5px] font-medium tracking-[0.04em] uppercase ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  )
}
