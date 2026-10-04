import { Moon, Sun } from 'lucide-react'
import { useTheme } from './ThemeProvider'

/**
 * ThemeToggle — animated dark/light toggle button.
 * Reads and flips the theme via useTheme().
 * Persisted to localStorage and respects prefers-color-scheme on first visit.
 *
 * Usage: <ThemeToggle /> anywhere inside <ThemeProvider>
 */
export function ThemeToggle({ className = '' }: { className?: string }) {
  const { theme, toggle } = useTheme()
  const isDark = theme === 'dark'

  return (
    <button
      onClick={toggle}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-pressed={!isDark}
      title={isDark ? 'Light mode' : 'Dark mode'}
      className={`
        relative flex h-8 w-8 items-center justify-center rounded-xl
        border border-[var(--as-border)] bg-[var(--as-glass-bg)]
        text-[var(--as-text-2)] transition-all
        hover:border-[var(--as-accent)] hover:text-[var(--as-accent)]
        hover:shadow-[0_0_16px_var(--as-accent-glow)]
        focus-visible:outline-2 focus-visible:outline-offset-2
        active:scale-95
        ${className}
      `}
      style={{ backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)' }}
    >
      {/* Sun icon — shown in dark mode (click to go light) */}
      <span
        className="absolute inset-0 flex items-center justify-center transition-all duration-300"
        style={{
          opacity: isDark ? 1 : 0,
          transform: isDark ? 'rotate(0deg) scale(1)' : 'rotate(-90deg) scale(0.5)',
        }}
        aria-hidden
      >
        <Sun size={14} strokeWidth={2} />
      </span>

      {/* Moon icon — shown in light mode (click to go dark) */}
      <span
        className="absolute inset-0 flex items-center justify-center transition-all duration-300"
        style={{
          opacity: isDark ? 0 : 1,
          transform: isDark ? 'rotate(90deg) scale(0.5)' : 'rotate(0deg) scale(1)',
        }}
        aria-hidden
      >
        <Moon size={14} strokeWidth={2} />
      </span>
    </button>
  )
}
