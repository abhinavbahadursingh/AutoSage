import { useEffect, useRef } from 'react'

/**
 * BackgroundField v2 — Aurora glassmorphism background
 *
 * Renders four large blurred gradient orbs that slowly drift around the
 * screen, creating an aurora/northern-lights effect behind glass surfaces.
 *
 * Parallax: mouse movement shifts each orb at different depths.
 * Grain:    a subtle noise texture is overlaid.
 * Reduced-motion: all animation is disabled when user prefers it.
 */
export function BackgroundField() {
  const rootRef = useRef<HTMLDivElement>(null)
  const orbRefs = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    const root = rootRef.current
    if (!root) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    let targetX = window.innerWidth / 2
    let targetY = window.innerHeight / 2
    let curX = targetX
    let curY = targetY
    let raf = 0

    const onMove = (e: MouseEvent) => {
      targetX = e.clientX
      targetY = e.clientY
    }

    const tick = () => {
      curX += (targetX - curX) * 0.04
      curY += (targetY - curY) * 0.04

      const nx = curX / window.innerWidth - 0.5
      const ny = curY / window.innerHeight - 0.5

      root.style.setProperty('--nx', nx.toFixed(4))
      root.style.setProperty('--ny', ny.toFixed(4))
      root.style.setProperty('--mx', `${curX.toFixed(1)}px`)
      root.style.setProperty('--my', `${curY.toFixed(1)}px`)

      raf = requestAnimationFrame(tick)
    }

    window.addEventListener('mousemove', onMove, { passive: true })
    raf = requestAnimationFrame(tick)

    return () => {
      window.removeEventListener('mousemove', onMove)
      cancelAnimationFrame(raf)
    }
  }, [])

  return (
    <div
      ref={rootRef}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0 overflow-hidden select-none"
      style={{ ['--nx' as string]: '0', ['--ny' as string]: '0' }}
    >
      {/* ── Dot grid texture layer ── */}
      <div
        className="bg-parallax anim-grid-drift absolute -inset-[40px] opacity-30"
        style={{ ['--depth' as string]: '0.2' }}
      >
        <div className="h-full w-full grid-fade" />
      </div>

      {/* ── Aurora orbs ── */}

      {/* Orb A — large violet blob, top-left */}
      <div
        ref={(el) => { orbRefs.current[0] = el }}
        className="bg-parallax anim-orb-a absolute"
        style={{
          ['--depth' as string]: '0.6',
          top: '-10%',
          left: '-5%',
          width: '65vw',
          height: '65vw',
          maxWidth: '900px',
          maxHeight: '900px',
          background: 'radial-gradient(circle at 40% 40%, var(--orb-a) 0%, transparent 70%)',
          filter: 'blur(80px)',
          willChange: 'transform',
        }}
      />

      {/* Orb B — teal blob, bottom-right */}
      <div
        ref={(el) => { orbRefs.current[1] = el }}
        className="bg-parallax anim-orb-b absolute"
        style={{
          ['--depth' as string]: '0.8',
          bottom: '-15%',
          right: '-8%',
          width: '60vw',
          height: '60vw',
          maxWidth: '800px',
          maxHeight: '800px',
          background: 'radial-gradient(circle at 60% 60%, var(--orb-b) 0%, transparent 70%)',
          filter: 'blur(70px)',
          willChange: 'transform',
        }}
      />

      {/* Orb C — deep violet, top-right (smaller, faster) */}
      <div
        ref={(el) => { orbRefs.current[2] = el }}
        className="bg-parallax anim-orb-c absolute"
        style={{
          ['--depth' as string]: '1.1',
          top: '15%',
          right: '5%',
          width: '40vw',
          height: '40vw',
          maxWidth: '550px',
          maxHeight: '550px',
          background: 'radial-gradient(circle at 50% 40%, var(--orb-c) 0%, transparent 70%)',
          filter: 'blur(60px)',
          willChange: 'transform',
        }}
      />

      {/* Orb D — soft teal, bottom-left */}
      <div
        ref={(el) => { orbRefs.current[3] = el }}
        className="bg-parallax anim-orb-d absolute"
        style={{
          ['--depth' as string]: '0.5',
          bottom: '5%',
          left: '10%',
          width: '45vw',
          height: '45vw',
          maxWidth: '600px',
          maxHeight: '600px',
          background: 'radial-gradient(circle at 50% 60%, var(--orb-d) 0%, transparent 70%)',
          filter: 'blur(65px)',
          willChange: 'transform',
        }}
      />

      {/* ── Vignette to darken edges and keep content legible ── */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse 90% 80% at 50% 50%, transparent 50%, color-mix(in oklch, var(--as-bg) 60%, transparent) 100%)',
        }}
      />

      {/* ── Cursor-following specular glow ── */}
      <div
        className="cursor-glow absolute inset-0"
        style={{
          background:
            'radial-gradient(350px circle at var(--mx, 50%) var(--my, 50%), color-mix(in oklch, var(--as-accent) 10%, transparent), transparent 70%)',
        }}
      />

      {/* ── Grain noise overlay ── */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E\")",
          backgroundSize: '128px 128px',
          opacity: 0.035,
          mixBlendMode: 'overlay',
        }}
      />
    </div>
  )
}
