import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

type Theme = 'dark' | 'light'

interface ThemeContextValue {
  theme: Theme
  toggle: () => void
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: 'dark',
  toggle: () => {},
})

function resolveInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'dark'
  const stored = window.localStorage.getItem('as-theme')
  if (stored === 'dark' || stored === 'light') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/** Wrap your app with this so any component can call useTheme(). */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(resolveInitialTheme)

  // Sync to <html> class and localStorage on change
  useEffect(() => {
    document.documentElement.className = theme
    window.localStorage.setItem('as-theme', theme)
    // Update theme-color meta for mobile browsers
    const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')
    if (meta) meta.content = theme === 'dark' ? '#0a0b10' : '#f5f5ff'
  }, [theme])

  const toggle = useCallback(() => {
    const flip = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
    // View Transitions API for a smooth crossfade; falls back to instant swap.
    const doc = document as Document & {
      startViewTransition?: (cb: () => void) => void
    }
    if (
      doc.startViewTransition &&
      !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      doc.startViewTransition(flip)
    } else {
      flip()
    }
  }, [])

  return <ThemeContext.Provider value={{ theme, toggle }}>{children}</ThemeContext.Provider>
}

/** Hook to read and toggle the current theme. */
export function useTheme() {
  return useContext(ThemeContext)
}
