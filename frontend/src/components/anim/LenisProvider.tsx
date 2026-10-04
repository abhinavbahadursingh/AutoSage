/**
 * LenisProvider — wraps the app with smooth inertial scrolling via Lenis.
 * Also exposes the Lenis instance through useLenis() for scroll-linked effects.
 */
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import Lenis from 'lenis'
import { LENIS, prefersReducedMotion } from '../../lib/animConfig'

const LenisCtx = createContext<Lenis | null>(null)

export function useLenis(): Lenis | null {
  return useContext(LenisCtx)
}

export function LenisProvider({ children }: { children: ReactNode }) {
  // State (not a ref) so consumers via useLenis() re-render with the instance.
  const [lenis, setLenis] = useState<Lenis | null>(null)

  useEffect(() => {
    // Don't initialise smooth scroll if user prefers reduced motion
    if (prefersReducedMotion()) return

    const instance = new Lenis({
      lerp: LENIS.lerp,
      duration: LENIS.duration,
      smoothWheel: LENIS.smoothWheel,
      // Lets inner page scroll containers (overflow-y-auto) scroll natively.
      // Without this Lenis swallows all wheel events and mouse scroll breaks.
      allowNestedScroll: LENIS.allowNestedScroll,
    })
    setLenis(instance)

    // RAF loop
    let raf = 0
    const tick = (time: number) => {
      instance.raf(time)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(raf)
      instance.destroy()
      setLenis(null)
    }
  }, [])

  return (
    <LenisCtx.Provider value={lenis}>
      {children}
    </LenisCtx.Provider>
  )
}
