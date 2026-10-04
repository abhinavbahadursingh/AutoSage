import { AnimatePresence, motion } from 'framer-motion'
import { useStore } from '../../store/context'
import { DUR, EASE } from '../../lib/animConfig'

const TONE_STYLES: Record<string, { border: string; dot: string }> = {
  neutral: { border: 'var(--as-border)', dot: 'var(--as-text-2)' },
  success: { border: 'color-mix(in oklch, var(--as-verify) 40%, transparent)', dot: 'var(--as-verify)' },
  warn:    { border: 'color-mix(in oklch, var(--as-warn) 40%, transparent)',   dot: 'var(--as-warn)' },
  error:   { border: 'color-mix(in oklch, var(--as-error) 40%, transparent)',  dot: 'var(--as-error)' },
}

export function ToastHost() {
  const { toasts, dismissToast } = useStore()

  return (
    <div className="pointer-events-none fixed top-4 right-4 z-50 flex w-[330px] flex-col gap-2.5">
      <AnimatePresence>
        {toasts.map((t) => {
          const { border, dot } = TONE_STYLES[t.tone] ?? TONE_STYLES.neutral
          return (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, x: 60, filter: 'blur(4px)' }}
              animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
              exit={{ opacity: 0, x: 40, filter: 'blur(4px)' }}
              transition={{ duration: DUR.fast, ease: EASE.out }}
              className="pointer-events-auto rounded-2xl border px-4 py-3 shadow-xl"
              style={{
                background: 'var(--as-glass-bg-2)',
                borderColor: border,
                backdropFilter: 'blur(24px) saturate(160%)',
                WebkitBackdropFilter: 'blur(24px) saturate(160%)',
                boxShadow: '0 16px 48px rgba(0,0,0,0.45), 0 1px 0 rgba(255,255,255,0.05) inset',
              }}
            >
              <div className="flex items-start gap-2.5">
                {/* Status dot */}
                <span
                  className="mt-[6px] h-1.5 w-1.5 shrink-0 rounded-full"
                  style={{ background: dot, boxShadow: `0 0 8px ${dot}` }}
                />
                <div className="min-w-0 flex-1">
                  <div className="text-[14.5px] font-semibold" style={{ color: 'var(--as-text)' }}>
                    {t.title}
                  </div>
                  {t.detail && (
                    <div className="mt-0.5 text-[13px] leading-snug" style={{ color: 'var(--as-text-2)' }}>
                      {t.detail}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => dismissToast(t.id)}
                  className="shrink-0 -mt-0.5 -mr-1 flex h-6 w-6 items-center justify-center rounded-lg text-[16px] leading-none transition-colors hover:bg-[var(--as-glass-bg)]"
                  style={{ color: 'var(--as-text-3)' }}
                  aria-label="Dismiss notification"
                >
                  ×
                </button>
              </div>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
