import type { ReactNode } from 'react'

export function EmptyState({
  icon,
  title,
  detail,
  action,
}: {
  icon?: ReactNode
  title: string
  detail?: string
  action?: ReactNode
}) {
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
      <div className="text-[16px] font-semibold" style={{ color: 'var(--as-text-2)' }}>{title}</div>
      {detail && (
        <div className="max-w-sm text-[14.5px] leading-relaxed" style={{ color: 'var(--as-text-3)' }}>
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
