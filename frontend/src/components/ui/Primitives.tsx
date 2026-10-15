import type { ReactNode } from 'react'

export function EmptyState({
  icon,
  title,
  detail,
  action,
  variant = 'plain',
}: {
  icon?: ReactNode
  title: string
  detail?: string
  action?: ReactNode
  /**
   * `plain` is the compact inline state used between content.
   * `feature` is the surface's own landing state — a framed glass panel with a
   * dot-grid wash, for pages where "nothing here yet" is what the visitor sees
   * first. Opt-in; every existing call site keeps `plain`.
   */
  variant?: 'plain' | 'feature'
}) {
  if (variant === 'feature') {
    return (
      <div className="flex items-center justify-center px-6 py-14">
        <div
          className="glass relative w-full max-w-[560px] overflow-hidden rounded-3xl px-8 py-12 text-center"
          style={{ borderColor: 'var(--as-glass-border)' }}
        >
          <div className="grid-fade pointer-events-none absolute inset-0 opacity-60" aria-hidden />
          <div
            className="pointer-events-none absolute -top-28 left-1/2 h-56 w-[460px] -translate-x-1/2 rounded-full"
            style={{
              background: 'radial-gradient(closest-side, var(--as-accent-glow), transparent)',
            }}
            aria-hidden
          />
          <div className="relative">
            <div
              className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border"
              style={{
                background: 'color-mix(in oklch, var(--as-accent) 10%, transparent)',
                borderColor: 'color-mix(in oklch, var(--as-accent) 26%, transparent)',
                color: 'var(--as-accent-hi)',
              }}
            >
              {icon}
            </div>
            <div className="text-[17px] font-semibold tracking-tight" style={{ color: 'var(--as-text)' }}>
              {title}
            </div>
            {detail && (
              <p className="mx-auto mt-2 max-w-[46ch] text-[14px] leading-relaxed" style={{ color: 'var(--as-text-2)' }}>
                {detail}
              </p>
            )}
            {action && <div className="mt-6 flex justify-center">{action}</div>}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center justify-center gap-2.5 px-6 py-16 text-center">
      <div
        className="mb-1 flex h-11 w-11 items-center justify-center rounded-2xl border"
        style={{
          background: 'color-mix(in oklch, var(--as-accent) 8%, transparent)',
          borderColor: 'var(--as-border)',
          color: 'var(--as-text-3)',
        }}
      >
        {icon}
      </div>
      <div className="text-[16px] font-semibold tracking-tight" style={{ color: 'var(--as-text)' }}>{title}</div>
      {detail && (
        <div className="max-w-sm text-[14.5px] leading-relaxed" style={{ color: 'var(--as-text-2)' }}>
          {detail}
        </div>
      )}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`relative overflow-hidden rounded-2xl ${className}`}
      style={{ background: 'var(--as-bg-3)' }}
    >
      <div
        className="absolute inset-0 -translate-x-full"
        style={{
          background: 'linear-gradient(90deg, transparent, color-mix(in oklch, var(--as-accent) 8%, transparent), transparent)',
          animation: 'sweep 1.6s ease-in-out infinite',
        }}
      />
    </div>
  )
}

export function KeyVal({ k, v, mono = true }: { k: string; v: ReactNode; mono?: boolean }) {
  return (
    <div
      className="flex items-baseline justify-between gap-3 border-b py-1.5 last:border-0"
      style={{ borderColor: 'var(--as-border)' }}
    >
      <span className="shrink-0 text-[13px]" style={{ color: 'var(--as-text-3)' }}>{k}</span>
      <span
        className={`min-w-0 truncate text-right text-[13.5px] ${mono ? 'mono' : ''}`}
        style={{ color: 'var(--as-text)' }}
      >
        {v}
      </span>
    </div>
  )
}

export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div
      className="flex items-center justify-between gap-3 border-b px-4 py-2.5"
      style={{ borderColor: 'var(--as-border)' }}
    >
      <h3 className="label-xs" style={{ color: 'var(--as-text-2)' }}>{children}</h3>
      {right}
    </div>
  )
}
