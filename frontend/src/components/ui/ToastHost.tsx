import { useStore } from '../../store/context'

const toneMap = {
  neutral: 'border-ink-500',
  success: 'border-verify-500',
  warn: 'border-warn-500',
  error: 'border-conflict-500',
} as const

const dotMap = {
  neutral: 'bg-paper-300',
  success: 'bg-verify-500',
  warn: 'bg-warn-500',
  error: 'bg-conflict-500',
} as const

export function ToastHost() {
  const { toasts, dismissToast } = useStore()
  if (toasts.length === 0) return null
  return (
    <div className="pointer-events-none fixed top-3 right-4 z-50 flex w-[320px] flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`anim-toast pointer-events-auto rounded-md border ${toneMap[t.tone]} bg-ink-800/95 px-3 py-2.5 shadow-[0_8px_24px_-12px_rgba(0,0,0,0.9)] backdrop-blur-[2px]`}
        >
          <div className="flex items-start gap-2">
            <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${dotMap[t.tone]}`} />
            <div className="min-w-0 flex-1">
              <div className="text-[15.5px] font-medium text-paper-100">{t.title}</div>
              {t.detail && <div className="mt-0.5 text-[14px] leading-snug text-paper-400">{t.detail}</div>}
            </div>
            <button
              onClick={() => dismissToast(t.id)}
              className="-mr-1 -mt-0.5 px-1 text-[18.5px] leading-none text-paper-500 transition hover:text-paper-200"
              aria-label="Dismiss"
            >
              ×
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
