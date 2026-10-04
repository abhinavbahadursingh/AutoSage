import type { ReactNode } from 'react'
import type { Tone } from '../../lib/tones'

const TONE_STYLES: Record<Tone, { bg: string; border: string; color: string }> = {
  neutral:  { bg: 'color-mix(in oklch, var(--as-text-3) 8%, transparent)',    border: 'var(--as-border)',                                          color: 'var(--as-text-2)'     },
  accent:   { bg: 'color-mix(in oklch, var(--as-accent) 12%, transparent)',    border: 'color-mix(in oklch, var(--as-accent) 30%, transparent)',     color: 'var(--as-accent-hi)'  },
  verify:   { bg: 'color-mix(in oklch, var(--as-verify) 10%, transparent)',    border: 'color-mix(in oklch, var(--as-verify) 30%, transparent)',     color: 'var(--as-verify)'     },
  warn:     { bg: 'color-mix(in oklch, var(--as-warn) 10%, transparent)',      border: 'color-mix(in oklch, var(--as-warn) 30%, transparent)',       color: 'var(--as-warn)'       },
  conflict: { bg: 'color-mix(in oklch, var(--as-error) 10%, transparent)',     border: 'color-mix(in oklch, var(--as-error) 30%, transparent)',      color: 'var(--as-error)'      },
  dim:      { bg: 'transparent',                                                border: 'var(--as-border)',                                          color: 'var(--as-text-3)'     },
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
  const s = TONE_STYLES[tone]
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-[2px] text-[11.5px] font-semibold tracking-[0.05em] uppercase ${className}`}
      style={{ background: s.bg, borderColor: s.border, color: s.color }}
    >
      {children}
    </span>
  )
}
