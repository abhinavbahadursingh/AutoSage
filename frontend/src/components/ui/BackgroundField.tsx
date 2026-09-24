import { useEffect, useRef } from 'react'
import type { CSSProperties } from 'react'

const CX = 100
const CY = 100

function polygonPoints(sides: number, radius: number, rot = -90): string {
  return Array.from({ length: sides }, (_, i) => {
    const a = ((rot + (i * 360) / sides) * Math.PI) / 180
    return `${(CX + radius * Math.cos(a)).toFixed(2)},${(CY + radius * Math.sin(a)).toFixed(2)}`
  }).join(' ')
}

const HEX = polygonPoints(6, 86, -90)
const HEX_INNER = polygonPoints(6, 48, -60)
const PENT = polygonPoints(5, 84, -90)
const TRI = polygonPoints(3, 88, -90)
const OCT = polygonPoints(8, 84, -22.5)

type Fig = {
  kind: 'hex' | 'pent' | 'tri' | 'oct' | 'circle' | 'squares' | 'grid-node' | 'phi'
  className: string
  anim: string
  depth: number
  style?: CSSProperties
}

const FIGS: Fig[] = [
  { kind: 'hex', className: 'top-[8%] left-[6%]', anim: 'anim-bg-spin', depth: 1, style: { animationDuration: '18s' } },
  { kind: 'pent', className: 'top-[18%] right-[8%]', anim: 'anim-bg-spin-rev', depth: 0.7, style: { animationDuration: '24s' } },
  { kind: 'tri', className: 'top-[52%] left-[4%]', anim: 'anim-bg-spin-drift', depth: 1.2, style: { animationDelay: '-4s' } },
  { kind: 'oct', className: 'bottom-[12%] right-[6%]', anim: 'anim-bg-spin', depth: 0.9, style: { animationDuration: '28s' } },
  { kind: 'circle', className: 'top-[64%] right-[14%]', anim: 'anim-bg-spin-drift-rev', depth: 1.1, style: { animationDelay: '-7s' } },
  { kind: 'squares', className: 'top-[38%] left-[14%]', anim: 'anim-bg-spin-rev', depth: 0.6, style: { animationDuration: '20s' } },
  { kind: 'phi', className: 'bottom-[24%] left-[22%]', anim: 'anim-bg-spin-drift', depth: 0.85, style: { animationDelay: '-2s', animationDuration: '30s' } },
  { kind: 'grid-node', className: 'top-[6%] left-[44%]', anim: 'anim-bg-spin', depth: 1.3, style: { animationDelay: '-3s', animationDuration: '16s' } },
  { kind: 'hex', className: 'bottom-[6%] left-[52%]', anim: 'anim-bg-spin-rev', depth: 0.75, style: { animationDuration: '22s' } },
  { kind: 'pent', className: 'top-[44%] right-[28%]', anim: 'anim-bg-spin-drift-rev', depth: 1.05, style: { animationDelay: '-9s', animationDuration: '26s' } },
]

function Figure({ kind }: { kind: Fig['kind'] }) {
  const stroke = 'currentColor'
  switch (kind) {
    case 'hex':
      return (
        <svg viewBox="0 0 200 200" className="h-full w-full">
          <polygon points={HEX} fill="none" stroke={stroke} strokeWidth="1.4" />
          <polygon points={HEX_INNER} fill="none" stroke={stroke} strokeWidth="1" opacity="0.6" />
          <line x1="14" y1="100" x2="186" y2="100" stroke={stroke} strokeWidth="0.7" opacity="0.4" />
          <line x1="100" y1="14" x2="100" y2="186" stroke={stroke} strokeWidth="0.7" opacity="0.4" />
        </svg>
      )
    case 'pent':
      return (
        <svg viewBox="0 0 200 200" className="h-full w-full">
          <polygon points={PENT} fill="none" stroke={stroke} strokeWidth="1.4" />
          {[0, 1, 2, 3, 4].map((i) =>
            [1, 2, 3, 4].map((j) => {
              if (j <= i) return null
              const a = ((-90 + (i * 360) / 5) * Math.PI) / 180
              const b = ((-90 + (j * 360) / 5) * Math.PI) / 180
              return (
                <line
                  key={`${i}-${j}`}
                  x1={CX + 84 * Math.cos(a)}
                  y1={CY + 84 * Math.sin(a)}
                  x2={CX + 84 * Math.cos(b)}
                  y2={CY + 84 * Math.sin(b)}
                  stroke={stroke}
                  strokeWidth="0.6"
                  opacity="0.35"
                />
              )
            })
          )}
        </svg>
      )
    case 'tri':
      return (
        <svg viewBox="0 0 200 200" className="h-full w-full">
          <polygon points={TRI} fill="none" stroke={stroke} strokeWidth="1.4" />
          <circle cx="100" cy="128" r="44" fill="none" stroke={stroke} strokeWidth="0.9" opacity="0.55" />
          <circle cx="100" cy="128" r="2.5" fill={stroke} />
          <line x1="100" y1="12" x2="100" y2="128" stroke={stroke} strokeWidth="0.6" strokeDasharray="3 4" opacity="0.5" />
        </svg>
      )
    case 'oct':
      return (
        <svg viewBox="0 0 200 200" className="h-full w-full">
          <polygon points={OCT} fill="none" stroke={stroke} strokeWidth="1.4" />
          <rect x="41" y="41" width="118" height="118" fill="none" stroke={stroke} strokeWidth="0.8" opacity="0.45" transform="rotate(45 100 100)" />
          <circle cx="100" cy="100" r="60" fill="none" stroke={stroke} strokeWidth="0.7" strokeDasharray="2 5" opacity="0.5" />
        </svg>
      )
    case 'circle':
      return (
        <svg viewBox="0 0 200 200" className="h-full w-full">
          <circle cx="100" cy="100" r="84" fill="none" stroke={stroke} strokeWidth="1.4" />
          <circle cx="100" cy="100" r="56" fill="none" stroke={stroke} strokeWidth="0.9" opacity="0.55" />
          <circle cx="100" cy="100" r="28" fill="none" stroke={stroke} strokeWidth="0.7" opacity="0.4" />
          <line x1="16" y1="100" x2="184" y2="100" stroke={stroke} strokeWidth="0.6" opacity="0.35" />
          <line x1="100" y1="16" x2="100" y2="184" stroke={stroke} strokeWidth="0.6" opacity="0.35" />
          <circle cx="100" cy="16" r="2.5" fill={stroke} />
          <circle cx="156" cy="100" r="2.5" fill={stroke} />
        </svg>
      )
    case 'squares':
      return (
        <svg viewBox="0 0 200 200" className="h-full w-full">
          <rect x="18" y="18" width="164" height="164" fill="none" stroke={stroke} strokeWidth="1.3" />
          <rect x="18" y="80" width="102" height="102" fill="none" stroke={stroke} strokeWidth="1" opacity="0.65" />
          <rect x="18" y="80" width="63" height="63" fill="none" stroke={stroke} strokeWidth="0.8" opacity="0.5" />
          <rect x="18" y="80" width="39" height="39" fill="none" stroke={stroke} strokeWidth="0.7" opacity="0.4" />
          <path
            d="M18 180 A164 164 0 0 1 182 180 A102 102 0 0 1 18 180 A63 63 0 0 1 18 117 A39 39 0 0 1 18 80"
            fill="none"
            stroke={stroke}
            strokeWidth="1"
            opacity="0.7"
          />
        </svg>
      )
    case 'phi':
      return (
        <svg viewBox="0 0 200 200" className="h-full w-full">
          <rect x="12" y="12" width="176" height="109" fill="none" stroke={stroke} strokeWidth="1.1" />
          <rect x="12" y="12" width="109" height="109" fill="none" stroke={stroke} strokeWidth="0.9" opacity="0.6" />
          <path
            d="M121 121 A109 109 0 0 0 12 12"
            fill="none"
            stroke={stroke}
            strokeWidth="1.2"
            opacity="0.8"
          />
          <path d="M121 121 A68 68 0 0 0 188 53" fill="none" stroke={stroke} strokeWidth="1" opacity="0.65" />
          <text x="150" y="112" fontSize="13" fill={stroke} opacity="0.55" fontFamily="monospace">
            φ
          </text>
        </svg>
      )
    case 'grid-node':
      return (
        <svg viewBox="0 0 200 200" className="h-full w-full">
          {[
            [40, 40],
            [160, 40],
            [40, 160],
            [160, 160],
            [100, 100],
          ].map(([x, y], i, arr) =>
            arr.slice(i + 1).map(([x2, y2], j) => (
              <line
                key={`${i}-${j}`}
                x1={x}
                y1={y}
                x2={x2}
                y2={y2}
                stroke={stroke}
                strokeWidth="0.7"
                opacity="0.4"
              />
            ))
          )}
          {[
            [40, 40],
            [160, 40],
            [40, 160],
            [160, 160],
            [100, 100],
          ].map(([x, y]) => (
            <circle key={`${x}-${y}`} cx={x} cy={y} r="4" fill="none" stroke={stroke} strokeWidth="1.2" />
          ))}
        </svg>
      )
  }
}

const SIZE: Record<Fig['kind'], string> = {
  hex: 'h-[180px] w-[180px]',
  pent: 'h-[160px] w-[160px]',
  tri: 'h-[140px] w-[140px]',
  oct: 'h-[150px] w-[150px]',
  circle: 'h-[150px] w-[150px]',
  squares: 'h-[140px] w-[140px]',
  phi: 'h-[170px] w-[170px]',
  'grid-node': 'h-[130px] w-[130px]',
}

export function BackgroundField() {
  const rootRef = useRef<HTMLDivElement>(null)
  const figRefs = useRef<(HTMLDivElement | null)[]>([])

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
      curX += (targetX - curX) * 0.07
      curY += (targetY - curY) * 0.07

      const nx = curX / window.innerWidth - 0.5
      const ny = curY / window.innerHeight - 0.5
      root.style.setProperty('--nx', nx.toFixed(4))
      root.style.setProperty('--ny', ny.toFixed(4))
      root.style.setProperty('--mx', `${curX.toFixed(1)}px`)
      root.style.setProperty('--my', `${curY.toFixed(1)}px`)

      for (const el of figRefs.current) {
        if (!el) continue
        const r = el.getBoundingClientRect()
        const d = Math.hypot(r.left + r.width / 2 - curX, r.top + r.height / 2 - curY)
        const prox = Math.max(0, Math.min(1, 1 - d / 280))
        el.style.setProperty('--prox', prox.toFixed(3))
      }

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
      <div className="bg-parallax absolute -inset-[56px]" style={{ ['--depth' as string]: '0.3' }}>
        <div className="anim-grid-drift h-full w-full grid-fade opacity-100" />
      </div>
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_60%_at_50%_40%,transparent_55%,color-mix(in_oklab,var(--color-ink-900)_70%,transparent)_100%)]" />
      <div className="absolute inset-0 text-accent-500/75">
        {FIGS.map((f, i) => (
          <div
            key={i}
            ref={(el) => {
              figRefs.current[i] = el
            }}
            className={`bg-fig absolute ${f.className} ${SIZE[f.kind]}`}
            style={{ ...f.style, ['--depth' as string]: String(f.depth) } as CSSProperties}
          >
            <div className={`h-full w-full ${f.anim}`} style={f.style}>
              <Figure kind={f.kind} />
            </div>
          </div>
        ))}
      </div>
      <div
        className="absolute inset-0 mix-blend-screen"
        style={{
          background:
            'radial-gradient(360px circle at var(--mx, 50%) var(--my, 50%), color-mix(in oklab, var(--color-accent-500) 13%, transparent), transparent 70%)',
        }}
      />
    </div>
  )
}
