/**
 * NodeNetwork — interactive canvas particle/node network for the hero.
 * Nodes drift slowly; lines draw between close nodes; mouse proximity
 * repels nodes slightly, creating an organic multi-agent graph feel.
 * Pure canvas — no Three.js dependency.
 */
import { useRef, useEffect } from 'react'
import { PARTICLES, getFlags, prefersReducedMotion } from '../../lib/animConfig'

interface NodeNetworkProps {
  className?: string
  accentColor?: string
  tealColor?: string
}

export function NodeNetwork({
  className = '',
  accentColor = '#8b5cf6',
  tealColor = '#2dd4bf',
}: NodeNetworkProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const flags = getFlags()

  useEffect(() => {
    if (!flags.particles || prefersReducedMotion()) return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let raf = 0
    let mx = -999, my = -999

    // ── Resize ──────────────────────────────────────────────────────────────
    const resize = () => {
      const pr = window.devicePixelRatio || 1
      canvas.width = canvas.offsetWidth * pr
      canvas.height = canvas.offsetHeight * pr
      ctx.scale(pr, pr)
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(canvas)

    // ── Nodes ────────────────────────────────────────────────────────────────
    type Node = {
      x: number; y: number
      vx: number; vy: number
      r: number
      color: string
      pulse: number
      pulseSpeed: number
    }

    const w = () => canvas.offsetWidth
    const h = () => canvas.offsetHeight

    const nodes: Node[] = Array.from({ length: PARTICLES.count }, () => ({
      x: Math.random() * w(),
      y: Math.random() * h(),
      vx: (Math.random() - 0.5) * PARTICLES.speed,
      vy: (Math.random() - 0.5) * PARTICLES.speed,
      r: PARTICLES.dotRadius * (0.7 + Math.random() * 0.6),
      color: Math.random() > 0.5 ? accentColor : tealColor,
      pulse: Math.random() * Math.PI * 2,
      pulseSpeed: 0.015 + Math.random() * 0.025,
    }))

    // ── Mouse ────────────────────────────────────────────────────────────────
    const onMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect()
      mx = e.clientX - rect.left
      my = e.clientY - rect.top
    }
    const onLeave = () => { mx = -999; my = -999 }
    canvas.addEventListener('mousemove', onMove, { passive: true })
    canvas.addEventListener('mouseleave', onLeave)

    // ── Draw loop ─────────────────────────────────────────────────────────────
    const tick = () => {
      const cw = w(), ch = h()
      ctx.clearRect(0, 0, cw, ch)

      // Update nodes
      for (const n of nodes) {
        n.pulse += n.pulseSpeed
        n.x += n.vx
        n.y += n.vy

        // Bounce off edges
        if (n.x < 0 || n.x > cw) n.vx *= -1
        if (n.y < 0 || n.y > ch) n.vy *= -1
        n.x = Math.max(0, Math.min(cw, n.x))
        n.y = Math.max(0, Math.min(ch, n.y))

        // Mouse repulsion (gentle)
        const dx = n.x - mx, dy = n.y - my
        const dist = Math.hypot(dx, dy)
        if (dist < 100 && dist > 0) {
          const force = (100 - dist) / 100 * 0.4
          n.vx += (dx / dist) * force
          n.vy += (dy / dist) * force
          // Dampen velocity
          n.vx *= 0.95
          n.vy *= 0.95
        }
      }

      // Draw edges between close nodes
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j]
          const dx = a.x - b.x, dy = a.y - b.y
          const dist = Math.hypot(dx, dy)
          if (dist < PARTICLES.connectDist) {
            const alpha = (1 - dist / PARTICLES.connectDist) * 0.35
            ctx.beginPath()
            ctx.strokeStyle = a.color.replace(')', `, ${alpha.toFixed(3)})`)
              .replace('rgb', 'rgba').replace('hsl', 'hsla')
            // If color is hex, parse manually
            ctx.strokeStyle = hexWithAlpha(a.color, alpha)
            ctx.lineWidth = 0.6
            ctx.moveTo(a.x, a.y)
            ctx.lineTo(b.x, b.y)
            ctx.stroke()
          }
        }
      }

      // Draw nodes
      for (const n of nodes) {
        const glow = Math.sin(n.pulse) * 0.25 + 0.6
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.r * (1 + Math.sin(n.pulse) * 0.18), 0, Math.PI * 2)
        ctx.fillStyle = hexWithAlpha(n.color, glow)
        ctx.fill()
        // Subtle outer glow
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.r * 3, 0, Math.PI * 2)
        ctx.fillStyle = hexWithAlpha(n.color, glow * 0.08)
        ctx.fill()
      }

      raf = requestAnimationFrame(tick)
    }

    raf = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      canvas.removeEventListener('mousemove', onMove)
      canvas.removeEventListener('mouseleave', onLeave)
    }
  }, [accentColor, tealColor, flags.particles])

  if (!flags.particles || prefersReducedMotion()) return null

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className={className}
      style={{ display: 'block', width: '100%', height: '100%', pointerEvents: 'auto' }}
    />
  )
}

/** Convert hex #rrggbb or #rgb to rgba(r,g,b,a) */
function hexWithAlpha(hex: string, a: number): string {
  // Already rgba
  if (hex.startsWith('rgba') || hex.startsWith('rgb')) return hex
  const h = hex.replace('#', '')
  const full = h.length === 3
    ? h.split('').map(c => c + c).join('')
    : h
  const r = parseInt(full.slice(0, 2), 16)
  const g = parseInt(full.slice(2, 4), 16)
  const b = parseInt(full.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${a.toFixed(3)})`
}
