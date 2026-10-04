/**
 * useNavScroll — returns whether the navbar should be visible and
 * whether it has scrolled past the initial position (for stronger blur).
 *
 * Hides on scroll-down, reappears on scroll-up.
 */
import { useEffect, useRef, useState } from 'react'

export function useNavScroll() {
  const [visible, setVisible] = useState(true)
  const [scrolled, setScrolled] = useState(false)
  const lastY = useRef(0)

  useEffect(() => {
    // capture:true so scrolls from inner overflow containers are seen too
    // (app pages scroll inside their own containers, not the window)
    const onScroll = (e: Event) => {
      const t = e.target as Document | Element | null
      const y = t instanceof Element ? t.scrollTop : window.scrollY
      setScrolled(y > 20)
      if (y < 10) { setVisible(true); lastY.current = y; return }
      if (y > lastY.current + 6) setVisible(false)
      else if (y < lastY.current - 4) setVisible(true)
      lastY.current = y
    }
    window.addEventListener('scroll', onScroll, { passive: true, capture: true })
    return () => window.removeEventListener('scroll', onScroll, { capture: true })
  }, [])

  return { visible, scrolled }
}
