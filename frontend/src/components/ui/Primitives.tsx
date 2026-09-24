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
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <div className="mb-1 flex h-9 w-9 items-center justify-center rounded-md border border-ink-600 bg-ink-850 text-paper-400">
        {icon}
      </div>
      <div className="text-[16px] font-medium text-paper-200">{title}</div>
      {detail && <div className="max-w-sm text-[15px] leading-relaxed text-paper-500">{detail}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`relative overflow-hidden rounded-sm bg-ink-750 ${className}`}>
    <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-ink-600/50 to-transparent [animation:sweep_1.6s_ease-in-out_infinite]" />
  </div>
}

export function KeyVal({ k, v, mono = true }: { k: string; v: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-ink-700/70 py-1.5 last:border-0">
      <span className="shrink-0 text-[13.5px] text-paper-400">{k}</span>
      <span className={`min-w-0 truncate text-right text-[14px] text-paper-100 ${mono ? 'mono' : ''}`}>{v}</span>
    </div>
  )
}

export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-ink-600 px-4 py-2.5">
      <h3 className="label-xs text-paper-300">{children}</h3>
      {right}
    </div>
  )
}
