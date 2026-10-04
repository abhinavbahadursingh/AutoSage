import { BackgroundField } from '../components/ui/BackgroundField'
import { Sidebar } from '../components/layout/Sidebar'
import { NewExperimentPage } from '../pages/NewExperiment'
import { WorkspacePage } from '../pages/Workspace'
import { HomePage } from '../pages/Home'
import { AgentDrawer } from '../components/workspace/AgentDrawer'
import { Badge } from '../components/ui/Badge'
import { Ctx, useStore } from '../store/context'
import { makeStore } from './store'
import { EXPERIMENT_NAME } from './fixture'
import {
  BAND,
  CAPTIONS,
  CLAIMS_AT,
  CURSOR_AT_BUTTON,
  CURSOR_IN,
  CURSOR_OUT,
  DRAWER_AT,
  HEIGHT,
  PRESS_AT,
  PRESS_OUT,
  SCENES,
  WIDTH,
  sceneAt,
  sceneOpacity,
} from './timeline'
import type { Scene, SceneId } from './timeline'

/* ------------------------------------------------------------------ layout */

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full w-full">
      <div className="hidden md:flex">
        <Sidebar />
      </div>
      <div className="flex h-full min-w-0 flex-1 flex-col">
        <main className="min-h-0 flex-1 overflow-hidden">
          <div className="h-full min-h-0">{children}</div>
        </main>
      </div>
    </div>
  )
}

function camera(id: SceneId, t: number, h: number) {
  const prog = (a: number, b: number) => Math.min(1, Math.max(0, (t - a) / (b - a)))
  const ease = (p: number) => p * p * (3 - 2 * p)

  switch (id) {
    case 'hook': {
      const s = 0.965 + 0.035 * ease(prog(0, 3.3))
      return { scale: s, tx: (WIDTH / 2) * (1 - s), ty: (h / 2) * (1 - s) }
    }
    case 'run': {
      const s = 0.97 + 0.03 * ease(prog(3.42, 7.7))
      return { scale: s, tx: (WIDTH / 2) * (1 - s), ty: (h / 2) * (1 - s) }
    }
    case 'agents': {
      const s =
        1 + 0.125 * ease(prog(7.82, 9.6)) + 0.015 * ease(prog(9.6, 13.25))
      return { scale: s, tx: WIDTH * (1 - s), ty: 0 }
    }
    case 'verify': {
      const s = 0.975 + 0.025 * ease(prog(13.37, 16.45))
      return { scale: s, tx: (WIDTH / 2) * (1 - s), ty: (h / 2) * (1 - s) }
    }
    case 'hero': {
      const s = 0.98 + 0.02 * ease(prog(16.57, 20))
      return { scale: s, tx: (WIDTH / 2) * (1 - s), ty: (h / 2) * (1 - s) }
    }
  }
}

function SceneBox({ scene, t, children }: { scene: Scene; t: number; children: React.ReactNode }) {
  const h = scene.band ? HEIGHT - BAND : HEIGHT
  const c = camera(scene.id, t, h)
  return (
    <div
      className="brag-scene"
      data-scene={scene.id}
      style={{ top: scene.band ? BAND : 0, height: h, opacity: sceneOpacity(scene, t) }}
    >
      <div
        className="brag-camera"
        style={{
          height: h,
          transform: `translate(${c.tx}px, ${c.ty}px) scale(${c.scale})`,
          background: scene.id === 'hero' ? undefined : 'rgba(11,12,14,0.68)',
        }}
      >
        {children}
      </div>
      {scene.id === 'hook' && <Cursor t={t} />}
    </div>
  )
}

/* ------------------------------------------------------------ scene pieces */

function Cursor({ t }: { t: number }) {
  if (t < CURSOR_IN || t > CURSOR_OUT) return null
  const fade =
    Math.min(1, (t - CURSOR_IN) / 0.18) * Math.min(1, (CURSOR_OUT - t) / 0.14)
  return (
    <div className="brag-overlay">
      <svg
        className="brag-cursor"
        data-brag-cursor
        viewBox="0 0 26 34"
        style={{ opacity: fade, left: 0, top: 0 }}
      >
        <path
          d="M2 1.6 L2 27.5 L8.6 21.6 L12.7 30.9 L17.2 28.9 L13.1 19.9 L21.6 19.4 Z"
          fill="#f2f4f6"
          stroke="#0b0c0e"
          strokeWidth="1.4"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  )
}

function ClaimsPanel() {
  const CLAIMS = [
    { id: 'clm_7f2a41', text: 'Model beats random baseline by 15%', conf: 0.97, sup: 3 },
    { id: 'clm_9c08de', text: 'Stratified CV used for imbalanced data', conf: 0.95, sup: 4 },
    { id: 'clm_2b55fa', text: 'No PII in features', conf: 0.92, sup: 2 },
  ]
  return (
    <section className="brag-claims anim-rise" data-brag-t0={String(CLAIMS_AT * 1000)}>
      <div className="overflow-hidden rounded-md border border-ink-600 bg-ink-900 shadow-[0_24px_60px_-30px_rgba(0,0,0,0.95)]">
        <div className="flex items-center justify-between border-b border-ink-600 px-4 py-2.5">
          <h3 className="label-xs text-paper-300">Experiment verification</h3>
          <span className="mono text-[12.5px] text-paper-500">POST /verification/experiment</span>
        </div>
        <div className="p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="verify">VERIFIED</Badge>
            <span className="mono text-[13px] text-paper-400">3/3 verified · conf 0.95</span>
          </div>
          <ul className="mt-3 flex flex-col gap-2">
            {CLAIMS.map((c, i) => (
              <li
                key={c.id}
                className="anim-rise rounded-sm border border-ink-700 bg-ink-850/70 px-3 py-2.5"
                style={{ animationDelay: `${0.16 + i * 0.11}s`, animationDuration: '0.5s' }}
              >
                <div className="flex items-start gap-2">
                  <Badge tone="verify">VERIFIED</Badge>
                  <p className="min-w-0 flex-1 text-[14.5px] leading-snug text-paper-200">{c.text}</p>
                </div>
                <p className="mono mt-1.5 text-[12.5px] text-paper-500">
                  {c.id} · conf {c.conf.toFixed(2)} · supporting {c.sup} · contradicting 0
                </p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}

/* ----------------------------------------------------------------- captions */

const CAPTION_LABELS = ['02 — the run', '03 — the trail', '04 — the proof']

function Captions({ t }: { t: number }) {
  const idx = CAPTIONS.findIndex((c) => t >= c.t0 - 0.02 && t <= c.t1)
  if (idx < 0) return null
  const cap = CAPTIONS[idx]
  const env = Math.min(1, Math.max(0, (t - (cap.t0 - 0.2)) / 0.22)) *
    Math.min(1, Math.max(0, (cap.t1 - t) / 0.22))
  const words = cap.text.split(' ')
  const rule = Math.min(1, Math.max(0, (t - (cap.t0 - 0.12)) / 0.3))
  const labelIn = Math.min(1, Math.max(0, (t - (cap.t0 + 0.1)) / 0.35))

  return (
    <div className="brag-band" style={{ opacity: env }}>
      <div className="brag-caption">
        <span
          className="rule"
          style={{ transform: `scaleX(${rule})`, transformOrigin: 'left center' }}
        />
        {words.map((w, i) => {
          const p = Math.min(1, Math.max(0, (t - (cap.t0 + i * 0.055)) / 0.32))
          const e = 1 - Math.pow(1 - p, 3)
          return (
            <span
              key={`${w}-${i}`}
              className="word"
              style={{ opacity: p, transform: `translateY(${(1 - e) * 16}px)` }}
            >
              {w}
            </span>
          )
        })}
      </div>
      <div
        className="mono absolute right-[56px] text-[13px] tracking-[0.2em] text-paper-500 uppercase"
        style={{ position: 'absolute', right: 56, opacity: labelIn }}
      >
        {CAPTION_LABELS[idx]}
      </div>
    </div>
  )
}

/* -------------------------------------------------------------------- video */

function SceneContent({ scene, t }: { scene: Scene; t: number }) {
  const exp = useStore().activeExperiment

  if (scene.id === 'hook') {
    return (
      <div data-brag-t0={String(scene.t0 * 1000)} style={{ display: 'contents' }}>
        <Shell>
          <NewExperimentPage />
        </Shell>
      </div>
    )
  }

  if (scene.id === 'hero') {
    return (
      <div data-brag-t0={String(scene.t0 * 1000)} style={{ display: 'contents' }}>
        <HomePage />
      </div>
    )
  }

  const verifier = exp?.nodes.find((n) => n.id === 'n-verification') ?? null

  return (
    <Shell>
      <WorkspacePage />
      {scene.id === 'agents' && t >= DRAWER_AT && exp && verifier && (
        <div data-brag-t0={String(DRAWER_AT * 1000)} style={{ display: 'contents' }}>
          <AgentDrawer experiment={exp} node={verifier} onClose={() => {}} />
        </div>
      )}
      {scene.id === 'verify' && t >= CLAIMS_AT && <ClaimsPanel />}
    </Shell>
  )
}

export function Video({ t }: { t: number }) {
  const scene = sceneAt(t)
  const store = makeStore(t)

  return (
    <Ctx.Provider value={store}>
      <BackgroundField />
      {scene && (
        <SceneBox key={scene.id} scene={scene} t={t}>
          <SceneContent scene={scene} t={t} />
        </SceneBox>
      )}
      <Captions t={t} />
    </Ctx.Provider>
  )
}
