import { flushSync } from 'react-dom'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import './brag.css'
import { Video } from './Video'
import {
  CURSOR_AT_BUTTON,
  CURSOR_IN,
  EVIDENCE_TAB_AT,
  PRESS_AT,
  PRESS_OUT,
  promptAt,
  sceneAt,
} from './timeline'

const root = createRoot(document.getElementById('root') as HTMLElement)

let sceneId: string | null = null
let sceneMap = new WeakMap<Animation, number>()
let evidenceTabClicked = false

const clamp = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v)
const smooth = (p: number) => p * p * (3 - 2 * p)

function render(t: number) {
  const sc = sceneAt(t)
  const id = sc?.id ?? null
  if (id !== sceneId) {
    sceneId = id
    sceneMap = new WeakMap()
    evidenceTabClicked = false
  }
  flushSync(() => {
    root.render(
      <MemoryRouter>
        <Video t={t} />
      </MemoryRouter>,
    )
  })
}

function domEffects(t: number) {
  const sc = sceneAt(t)

  if (sc?.id === 'hook') {
    const ta = document.querySelector<HTMLTextAreaElement>('textarea')
    const want = promptAt(t)
    if (ta && ta.value !== want) {
      const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set
      setter?.call(ta, want)
      flushSync(() => ta.dispatchEvent(new Event('input', { bubbles: true })))
    }

    const btn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Run Experiment'),
    )
    if (btn) {
      const r = btn.getBoundingClientRect()
      const pressed = t >= PRESS_AT && t <= PRESS_OUT
      btn.style.transform = pressed ? 'scale(0.965)' : ''
      btn.style.filter = pressed ? 'brightness(1.2)' : ''

      const svg = document.querySelector<SVGSVGElement>('[data-brag-cursor]')
      if (svg && r.width > 0) {
        const p = smooth(clamp((t - (CURSOR_IN + 0.1)) / (CURSOR_AT_BUTTON - CURSOR_IN - 0.1)))
        const tx = r.left + r.width * 0.68
        const ty = r.top + r.height * 0.74
        svg.style.left = `${1712 + (tx - 1712) * p}px`
        svg.style.top = `${1016 + (ty - 1016) * p}px`
      }
    }
  }

  if (sc?.id === 'agents' && t >= EVIDENCE_TAB_AT && !evidenceTabClicked) {
    const btn = Array.from(document.querySelectorAll('aside nav button')).find(
      (b) => b.textContent?.trim() === 'Evidence',
    )
    if (btn) {
      evidenceTabClicked = true
      const aside = btn.closest('aside')
      const before = aside ? new Set(aside.querySelectorAll('*')) : null
      flushSync(() => btn.click())
      if (aside && before) {
        const t0 = String(EVIDENCE_TAB_AT * 1000)
        for (const el of aside.querySelectorAll('*')) {
          if (!before.has(el)) el.setAttribute('data-brag-t0', t0)
        }
      }
    }
  }
}

function seek(t: number) {
  const sc = sceneAt(t)
  const sceneLocal = sc ? (t - sc.t0) * 1000 : 0
  const globalMs = t * 1000

  for (const a of document.getAnimations()) {
    const target = (a.effect ? a.effect.target : null) as Element | null
    try {
      a.pause()
    } catch {
      /* some effects refuse time travel */
    }

    const declared =
      target && typeof target.closest === 'function'
        ? target.closest('[data-brag-t0]')
        : null
    if (declared) {
      const t0 = Number((declared as HTMLElement).dataset.bragT0)
      if (Number.isFinite(t0)) {
        a.currentTime = globalMs - t0
        continue
      }
    }

    const inScene = Boolean(
      target && typeof target.closest === 'function' && target.closest('[data-scene]'),
    )
    if (!inScene) {
      a.currentTime = globalMs
      continue
    }

    let birth = sceneMap.get(a)
    if (birth === undefined) {
      birth = sceneLocal
      sceneMap.set(a, birth)
    }
    a.currentTime = sceneLocal - birth
  }
}

const nextPaint = () =>
  new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
  })

const w = window as unknown as { __frame?: (t: number) => Promise<void> }

w.__frame = async (t: number) => {
  render(t)
  domEffects(t)
  await nextPaint()
  seek(t)
}
