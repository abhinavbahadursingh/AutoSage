import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Loader2, Sparkles, ShieldCheck, Repeat2, FlaskConical, Zap } from 'lucide-react'
import { Logo } from '../components/layout/Sidebar'
import { ThemeToggle } from '../components/ui/ThemeToggle'
import { useStore } from '../store/context'
import { STAGE_META } from '../data/experiments'

// Animation components
import { RevealBlock, RevealList } from '../components/anim/RevealBlock'
import { SplitText } from '../components/anim/SplitText'
import { TiltCard } from '../components/anim/TiltCard'
import { CountUp } from '../components/anim/CountUp'
import { TypewriterText } from '../components/anim/TypewriterText'
import { NodeNetwork } from '../components/anim/NodeNetwork'
import { AgentPipelineDiagram } from '../components/anim/AgentPipelineDiagram'
import { VerificationChecklist } from '../components/anim/VerificationChecklist'
import { TerminalPanel } from '../components/anim/TerminalPanel'
import { Leaderboard } from '../components/anim/Leaderboard'
import { MetricChart } from '../components/anim/MetricChart'
import { useNavScroll } from '../components/anim/useNavScroll'
import { useMagnetic } from '../components/anim/useMagnetic'
import { SectionNav } from '../components/anim/SectionNav'
import { loginAsGuest } from '../lib/guestAuth'
import { DUR, EASE } from '../lib/animConfig'

// ── Data ─────────────────────────────────────────────────────────────────────

const PROCESS = ['Natural Language', 'Agent Reasoning', 'Experiment', 'Verification', 'Reproducible Pipeline']

const CONCEPTS = [
  {
    n: '01', icon: Sparkles, title: 'Understand',
    body: "AutoSage interprets the user's ML objective and dataset, planning a structured task graph before any agent executes.",
    color: 'var(--as-accent)', glow: 'var(--as-accent-glow)',
  },
  {
    n: '02', icon: FlaskConical, title: 'Experiment',
    body: 'Specialized agents prepare data, select models, test approaches, and evaluate results — each in its own isolated stage.',
    color: 'var(--as-teal)', glow: 'var(--as-teal-glow)',
  },
  {
    n: '03', icon: ShieldCheck, title: 'Verify',
    body: 'Important decisions are checked against evidence and recorded in an auditable, immutable trail. Conflicts are quarantined, not hidden.',
    color: 'var(--as-verify)', glow: 'rgba(16,185,129,0.25)',
  },
]

const FOCUS = [
  'Evidence-backed decisions',
  'Independent verification',
  'Reproducible experiments',
  'Reusable experience from previous runs',
]

const JOURNEY = [
  { n: '01', title: 'Describe your problem',          note: 'Plain language, no DSL.' },
  { n: '02', title: 'AutoSage plans the experiment',  note: 'A task graph of stages.' },
  { n: '03', title: 'Specialized agents execute it',  note: 'Each agent owns one stage.' },
  { n: '04', title: 'Results are empirically tested', note: 'Cross-validation and holdout.' },
  { n: '05', title: 'Decisions are verified',         note: 'Claims recomputed independently.' },
  { n: '06', title: 'A reproducible pipeline',        note: 'Seeded, signed, replayable.' },
]

const STATS = [
  { value: 9,    suffix: '',   label: 'Specialized Agents' },
  { value: 99.1, suffix: '%',  label: 'Verification Rate',  decimals: 1 },
  { value: 3,    suffix: 'x',  label: 'Faster than manual' },
  { value: 100,  suffix: '%',  label: 'Reproducible' },
]

const EXAMPLE = 'Predict customer churn from my dataset and optimize for recall.'

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionLabel({ index, title }: { index: string; title: string }) {
  return (
    <div className="mb-10 flex items-center gap-4">
      <span className="mono text-[12px]" style={{ color: 'var(--as-teal)' }}>{index}</span>
      <span className="h-px flex-1" style={{ background: 'var(--as-border)' }} />
      <span className="text-[12px] font-semibold tracking-[0.16em] uppercase" style={{ color: 'var(--as-text-3)' }}>
        {title}
      </span>
    </div>
  )
}

function MagneticButton({ children, onClick, disabled, className = '', style = {} }: {
  children: React.ReactNode; onClick?: () => void; disabled?: boolean; className?: string; style?: React.CSSProperties
}) {
  const { ref, x, y, onMouseMove, onMouseLeave } = useMagnetic(0.3)
  return (
    <motion.button
      ref={ref as React.RefObject<HTMLButtonElement>}
      onClick={onClick}
      disabled={disabled}
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
      style={{ x, y, ...style }}
      whileTap={{ scale: 0.96 }}
      className={`${className} hover-icon`}
      data-cursor="Run"
    >
      {children}
    </motion.button>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export function HomePage() {
  const navigate = useNavigate()
  const { createAndRun, busy, authReady, authError, user, setUser, setAuthError, toast } = useStore()
  const [prompt, setPrompt] = useState('')
  const [loginBusy, setLoginBusy] = useState(false)
  const { visible, scrolled } = useNavScroll()

  // Direct demo login from the home page: already signed in → open the
  // workspace; otherwise mint a guest session inline, no /login detour.
  const demoLogin = async () => {
    if (user) {
      navigate('/workspace')
      return
    }
    setLoginBusy(true)
    try {
      const guest = await loginAsGuest()
      setUser(guest)
      setAuthError(null)
      toast({ title: 'Welcome, Guest!', detail: 'You have full access to all features.', tone: 'success' })
      navigate('/workspace')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Demo login failed'
      setAuthError(msg)
      toast({ title: 'Demo login failed', detail: msg, tone: 'error' })
    } finally {
      setLoginBusy(false)
    }
  }

  const start = async (text?: string) => {
    const body = (text ?? prompt).trim() || EXAMPLE
    try {
      await createAndRun({
        prompt: body,
        dataset: 'telco_churn_2024.csv',
        target: 'churn',
        metric: 'recall',
        budget: '12 fit-min',
        verificationLevel: 'strict',
      })
      navigate('/workspace')
    } catch { /* toast already shown */ }
  }

  return (
    <div className="relative h-full w-full flex-1 overflow-y-auto" style={{ color: 'var(--as-text)' }}>
      <div className="relative z-10">

        {/* ── Sticky glass navbar — hides on scroll-down ── */}
        <motion.header
          animate={{ y: visible ? 0 : -80, opacity: visible ? 1 : 0 }}
          transition={{ duration: DUR.fast, ease: EASE.out }}
          className="sticky top-0 z-30 border-b"
          style={{
            background: scrolled ? 'var(--as-glass-bg-2)' : 'var(--as-glass-bg)',
            borderColor: 'var(--as-border)',
            backdropFilter: `blur(${scrolled ? '28px' : '16px'}) saturate(var(--as-glass-sat))`,
            WebkitBackdropFilter: `blur(${scrolled ? '28px' : '16px'}) saturate(var(--as-glass-sat))`,
            transition: 'background 0.3s, backdrop-filter 0.3s',
          }}
        >
          <div className="mx-auto flex h-[62px] max-w-[1200px] items-center justify-between px-6 sm:px-8">
            <Logo />
            <SectionNav />
            <div className="flex items-center gap-4">
              <span className="mono hidden text-[13px] sm:block" style={{ color: 'var(--as-text-3)' }}>
                {authError ? 'auth error' : authReady ? `${STAGE_META.length} stages · engine online` : 'connecting…'}
              </span>
              <MagneticButton
                onClick={() => void demoLogin()}
                disabled={loginBusy}
                className="btn-pill btn-ghost text-[14px]"
                style={{
                  height: '36px',
                  borderColor: 'color-mix(in oklch, var(--as-verify) 35%, transparent)',
                  color: 'var(--as-verify)',
                }}
              >
                {loginBusy ? (
                  <><Loader2 size={14} className="animate-spin" /> Logging in…</>
                ) : user ? (
                  <>Open Workspace <ArrowRight size={14} /></>
                ) : (
                  <><Zap size={14} /> Demo Login</>
                )}
              </MagneticButton>
              <span className="hidden md:block">
                <MagneticButton
                  onClick={() => void start()}
                  disabled={busy}
                  className="btn-pill btn-ghost text-[14px]"
                  style={{ height: '36px' }}
                >
                  {busy ? 'Starting…' : 'Start Experiment'}
                </MagneticButton>
              </span>
              <ThemeToggle />
            </div>
          </div>
        </motion.header>

        {/* ── Hero ── */}
        <section className="relative mx-auto grid max-w-[1200px] grid-cols-1 gap-16 px-6 pt-24 pb-28 sm:px-8 lg:grid-cols-[1fr_300px] lg:gap-20 overflow-hidden">

          {/* Node network canvas — behind hero text */}
          <div className="pointer-events-none absolute inset-0 opacity-30" aria-hidden>
            <NodeNetwork accentColor="#8b5cf6" tealColor="#2dd4bf" />
          </div>

          <div className="relative z-10">
            {/* Eyebrow pill */}
            <RevealBlock delay={0}>
              <motion.div
                className="inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-[12.5px] font-medium mb-8"
                style={{
                  background: 'color-mix(in oklch, var(--as-accent) 10%, transparent)',
                  borderColor: 'var(--as-border-hi)',
                  color: 'var(--as-accent-hi)',
                }}
                whileHover={{ scale: 1.04 }}
              >
                <motion.span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: 'var(--as-teal)' }}
                  animate={{ opacity: [1, 0.4, 1] }}
                  transition={{ repeat: Infinity, duration: 1.6 }}
                />
                Verified Multi-Agent AutoML
              </motion.div>
            </RevealBlock>

            {/* Headline with SplitText + typewriter */}
            <RevealBlock delay={0.1}>
              <h1
                className="text-[clamp(2.4rem,5.5vw,4rem)] leading-[1.07] font-semibold tracking-tight max-w-[18ch]"
                style={{ color: 'var(--as-text)' }}
              >
                <SplitText
                  text="From a question to a"
                  tag="span"
                  by="words"
                  style={{ display: 'block' }}
                />{' '}
                <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: '0.25em', flexWrap: 'wrap' }}>
                  <TypewriterText
                    words={['verified', 'reproducible', 'auditable', 'explainable']}
                    className="text-gradient"
                  />{' '}
                  <SplitText text="ML pipeline." tag="span" by="words" delay={0.3} />
                </span>
              </h1>
            </RevealBlock>

            <RevealBlock delay={0.25}>
              <p className="mt-7 max-w-[58ch] text-[17px] leading-[1.8]" style={{ color: 'var(--as-text-2)' }}>
                AutoSage turns natural-language machine learning tasks into reproducible experiments using
                specialized AI agents, empirical testing, and independent verification.
              </p>
            </RevealBlock>

            <RevealBlock delay={0.35}>
              <div className="mt-10 flex flex-wrap items-center gap-3">
                <MagneticButton
                  onClick={() => void start()}
                  disabled={busy}
                  className="btn-pill btn-primary"
                >
                  {busy ? 'Starting…' : 'Start an Experiment'}
                  <ArrowRight size={14} />
                </MagneticButton>
                <motion.a
                  href="#how"
                  className="btn-pill btn-ghost"
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                >
                  How it works
                </motion.a>
              </div>
            </RevealBlock>
          </div>

          {/* Process steps sidebar */}
          <ol
            className="relative hidden flex-col pl-8 lg:flex z-10"
            style={{ borderLeft: '1px solid var(--as-border)' }}
          >
            <motion.span
              className="anim-travel-y absolute -left-[3px] h-[5px] w-[5px] rounded-full"
              style={{ background: 'var(--as-accent)' }}
            />
            <RevealList
              items={PROCESS}
              stagger={0.1}
              render={(step, i) => (
                <li key={String(step)} className="relative py-[18px]">
                  <span
                    className="absolute top-[26px] -left-[calc(2rem+3.5px)] h-[7px] w-[7px] rounded-full border"
                    style={{
                      borderColor: i === PROCESS.length - 1 ? 'var(--as-accent)' : 'var(--as-border)',
                      background: i === PROCESS.length - 1 ? 'var(--as-accent-lo)' : 'var(--as-bg)',
                      boxShadow: i === PROCESS.length - 1 ? '0 0 10px var(--as-accent-glow)' : 'none',
                    }}
                  />
                  <div className="mono text-[11.5px] tracking-[0.14em]" style={{ color: 'var(--as-text-3)' }}>
                    {`0${i + 1}`}
                  </div>
                  <div
                    className={`mt-1 text-[15.5px] font-medium ${i === PROCESS.length - 1 ? 'text-gradient' : ''}`}
                    style={{ color: i === PROCESS.length - 1 ? undefined : 'var(--as-text-2)' }}
                  >
                    {String(step)}
                  </div>
                </li>
              )}
            />
          </ol>
        </section>

        {/* ── Stats bar ── */}
        <RevealBlock>
          <section
            className="border-y"
            style={{ borderColor: 'var(--as-border)', background: 'color-mix(in oklch, var(--as-accent) 3%, transparent)' }}
          >
            <div className="mx-auto max-w-[1200px] px-6 sm:px-8">
              <div className="grid grid-cols-2 divide-x divide-y md:grid-cols-4 md:divide-y-0"
                style={{ '--tw-divide-opacity': '1', borderColor: 'var(--as-border)' } as React.CSSProperties}>
                {STATS.map((s) => (
                  <div key={s.label} className="flex flex-col items-center py-8 gap-1">
                    <span
                      className="mono tnum text-[2.6rem] font-bold leading-none text-gradient"
                    >
                      <CountUp to={s.value} decimals={s.decimals ?? 0} suffix={s.suffix} />
                    </span>
                    <span className="text-[13px] mt-1" style={{ color: 'var(--as-text-3)' }}>{s.label}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </RevealBlock>

        {/* ── What is AutoSage — glass tilt cards ── */}
        <section className="border-t" style={{ borderColor: 'var(--as-border)' }}>
          <div className="mx-auto max-w-[1200px] px-6 py-24 sm:px-8">
            <RevealBlock><SectionLabel index="01" title="What is AutoSage?" /></RevealBlock>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
              {CONCEPTS.map((c, i) => {
                const Icon = c.icon
                return (
                  <TiltCard
                    key={c.title}
                    className="glass grain glow-border-spin relative rounded-3xl p-7 overflow-hidden"
                    style={{ boxShadow: `var(--as-glass-shadow), 0 0 40px color-mix(in oklch, ${c.glow} 50%, transparent)` }}
                    glowColor={c.glow}
                  >
                    <RevealBlock delay={i * 0.12}>
                      <div
                        className="mb-5 inline-flex h-10 w-10 items-center justify-center rounded-2xl"
                        style={{
                          background: `color-mix(in oklch, ${c.color} 12%, transparent)`,
                          border: `1px solid color-mix(in oklch, ${c.color} 30%, transparent)`,
                          color: c.color,
                          boxShadow: `0 0 16px color-mix(in oklch, ${c.color} 20%, transparent)`,
                        }}
                      >
                        <Icon size={18} strokeWidth={1.7} />
                      </div>
                      <div className="mono text-[11.5px] tracking-widest mb-2" style={{ color: c.color }}>{c.n}</div>
                      <h3 className="text-[17px] font-semibold mb-3" style={{ color: 'var(--as-text)' }}>{c.title}</h3>
                      <p className="text-[15px] leading-[1.75]" style={{ color: 'var(--as-text-2)' }}>{c.body}</p>
                      <div
                        className={`pointer-events-none absolute -top-20 -right-20 h-40 w-40 rounded-full opacity-30 ${i % 2 ? 'anim-float-b' : 'anim-float-a'}`}
                        style={{ background: `radial-gradient(circle, ${c.color} 0%, transparent 70%)`, filter: 'blur(30px)' }}
                      />
                    </RevealBlock>
                  </TiltCard>
                )
              })}
            </div>
          </div>
        </section>

        {/* ── Why AutoSage ── */}
        <section className="border-t" style={{ borderColor: 'var(--as-border)', background: 'color-mix(in oklch, var(--as-accent) 3%, transparent)' }}>
          <div className="mx-auto max-w-[1200px] px-6 py-24 sm:px-8">
            <RevealBlock><SectionLabel index="02" title="Why AutoSage?" /></RevealBlock>
            <div className="grid grid-cols-1 gap-12 lg:grid-cols-[1.4fr_1fr] lg:gap-20">
              <RevealBlock delay={0.1}>
                <p className="max-w-[54ch] text-[clamp(1.1rem,2.5vw,1.4rem)] leading-[1.75] font-light" style={{ color: 'var(--as-text-2)' }}>
                  Traditional AutoML automates training, but users cannot clearly understand{' '}
                  <em className="not-italic font-semibold" style={{ color: 'var(--as-text)' }}>why</em>{' '}
                  a pipeline was selected or whether an AI-generated decision is trustworthy.
                </p>
              </RevealBlock>
              <RevealList
                items={FOCUS}
                stagger={0.1}
                render={(f, i) => (
                  <li key={String(f)} className="flex items-center gap-4 border-b py-4 first:border-t" style={{ borderColor: 'var(--as-border)' }}>
                    <span className="mono text-[11px] shrink-0" style={{ color: 'var(--as-text-3)' }}>{`0${i + 1}`}</span>
                    <span className="text-[15.5px]" style={{ color: 'var(--as-text-2)' }}>{String(f)}</span>
                    <motion.span
                      className="ml-auto h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{ background: 'var(--as-accent)' }}
                      animate={{ boxShadow: ['0 0 0px var(--as-accent-glow)', '0 0 10px var(--as-accent-glow)', '0 0 0px var(--as-accent-glow)'] }}
                      transition={{ repeat: Infinity, duration: 2.2, delay: i * 0.4 }}
                    />
                  </li>
                )}
              />
            </div>
          </div>
        </section>

        {/* ── Agent Pipeline — sticky scrolling diagram ── */}
        <section id="pipeline" className="scroll-mt-20 border-t" style={{ borderColor: 'var(--as-border)' }}>
          <div className="mx-auto max-w-[1200px] px-6 pt-24 pb-4 sm:px-8">
            <RevealBlock><SectionLabel index="03" title="The Multi-Agent Pipeline" /></RevealBlock>
            <RevealBlock delay={0.1}>
              <p className="max-w-[54ch] text-[16px] leading-relaxed mb-12" style={{ color: 'var(--as-text-2)' }}>
                Scroll through to watch each specialist agent activate and pass work to the next.
              </p>
            </RevealBlock>
          </div>
          {/* Sticky diagram — owns its tall scroll track internally */}
          <AgentPipelineDiagram />
        </section>

        {/* ── How it works ── */}
        <section id="how" className="scroll-mt-20 border-t" style={{ borderColor: 'var(--as-border)' }}>
          <div className="mx-auto max-w-[1200px] px-6 py-24 sm:px-8">
            <RevealBlock><SectionLabel index="04" title="How it works" /></RevealBlock>
            <div className="relative">
              <div className="absolute top-[7px] right-0 left-0 hidden h-px md:block" style={{ background: 'var(--as-border)' }}>
                <span className="anim-travel-x absolute -top-[2px] h-[5px] w-[5px] rounded-full" style={{ background: 'var(--as-accent)' }} />
              </div>
              <RevealList
                className="grid grid-cols-1 gap-x-6 gap-y-9 sm:grid-cols-2 lg:grid-cols-6"
                items={JOURNEY}
                stagger={0.08}
                render={(s) => {
                  const step = s as (typeof JOURNEY)[0]
                  return (
                    <li className="relative">
                      <span className="relative z-10 flex h-[14px] w-[14px] rounded-full border items-center justify-center"
                        style={{ borderColor: 'var(--as-border-hi)', background: 'var(--as-bg-2)', boxShadow: '0 0 10px var(--as-accent-glow)' }}>
                        <span className="h-[6px] w-[6px] rounded-full" style={{ background: 'var(--as-accent)' }} />
                      </span>
                      <div className="mono mt-5 text-[12px] tracking-[0.12em]" style={{ color: 'var(--as-teal)' }}>{step.n}</div>
                      <h3 className="mt-2 text-[15.5px] leading-snug font-medium" style={{ color: 'var(--as-text)' }}>{step.title}</h3>
                      <p className="mt-1.5 text-[14px] leading-relaxed" style={{ color: 'var(--as-text-3)' }}>{step.note}</p>
                    </li>
                  )
                }}
              />
            </div>
          </div>
        </section>

        {/* ── Domain demo: Terminal + Verification + Leaderboard + Curves ── */}
        <section id="demo" className="scroll-mt-20 border-t" style={{ borderColor: 'var(--as-border)', background: 'color-mix(in oklch, var(--as-teal) 3%, transparent)' }}>
          <div className="mx-auto max-w-[1200px] px-6 py-24 sm:px-8">
            <RevealBlock><SectionLabel index="05" title="See it in action" /></RevealBlock>
            <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
              <RevealBlock delay={0.05}>
                <h3 className="text-[18px] font-semibold mb-4" style={{ color: 'var(--as-text)' }}>Live experiment log</h3>
                <TerminalPanel />
              </RevealBlock>
              <RevealBlock delay={0.15}>
                <h3 className="text-[18px] font-semibold mb-4" style={{ color: 'var(--as-text)' }}>Verification pipeline</h3>
                <div className="glass grain rounded-3xl p-7" style={{ boxShadow: 'var(--as-glass-shadow)' }}>
                  <VerificationChecklist />
                </div>
              </RevealBlock>
            </div>
            <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-2">
              <RevealBlock delay={0.05}>
                <h3 className="text-[18px] font-semibold mb-4" style={{ color: 'var(--as-text)' }}>Model leaderboard</h3>
                <div className="glass grain rounded-3xl p-7" style={{ boxShadow: 'var(--as-glass-shadow)' }}>
                  <Leaderboard />
                </div>
              </RevealBlock>
              <RevealBlock delay={0.15}>
                <h3 className="text-[18px] font-semibold mb-4" style={{ color: 'var(--as-text)' }}>Learning curves</h3>
                <div className="glass grain rounded-3xl p-7" style={{ boxShadow: 'var(--as-glass-shadow)' }}>
                  <MetricChart />
                </div>
              </RevealBlock>
            </div>
          </div>
        </section>

        {/* ── Research concepts ── */}
        <section className="border-t" style={{ borderColor: 'var(--as-border)' }}>
          <div className="mx-auto max-w-[1200px] px-6 py-24 sm:px-8">
            <RevealBlock><SectionLabel index="06" title="Research concepts" /></RevealBlock>
            <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
              {[
                {
                  tag: 'Concept A', title: 'Evidence & Reasoning Trail',
                  quote: '"Every important decision leaves an inspectable trail."',
                  body: 'Claims, their sources, and the result of independent recomputation are stored together — including conflicts, quarantined rather than hidden.',
                  icon: ShieldCheck, color: 'var(--as-accent)', glow: 'var(--as-accent-glow)',
                },
                {
                  tag: 'Concept B', title: 'Experience Memory',
                  quote: '"Verified experience from previous experiments can inform future ones."',
                  body: 'What worked, what failed, and why a prior run is trustworthy — searchable before a new experiment starts.',
                  icon: Repeat2, color: 'var(--as-teal)', glow: 'var(--as-teal-glow)',
                },
              ].map(({ tag, title, quote, body, icon: Icon, color, glow }, i) => (
                <TiltCard
                  key={tag}
                  className="glass grain glow-border-spin rounded-3xl p-8"
                  style={{ boxShadow: `var(--as-glass-shadow), 0 0 40px color-mix(in oklch, ${glow} 40%, transparent)` }}
                  glowColor={glow}
                >
                  <RevealBlock delay={i * 0.12}>
                    <div className="mono text-[11px] tracking-[0.14em] uppercase mb-3 flex items-center gap-2" style={{ color: 'var(--as-text-3)' }}>
                      <Icon size={13} style={{ color }} />
                      {tag}
                    </div>
                    <h3 className="text-[21px] font-semibold tracking-tight mb-4" style={{ color: 'var(--as-text)' }}>{title}</h3>
                    <p className="text-[16px] leading-[1.7] italic mb-4 pl-4 border-l-2" style={{ borderColor: color, color: 'var(--as-text-2)' }}>{quote}</p>
                    <p className="text-[14.5px] leading-[1.75]" style={{ color: 'var(--as-text-3)' }}>{body}</p>
                  </RevealBlock>
                </TiltCard>
              ))}
            </div>
          </div>
        </section>

        {/* ── CTA ── */}
        <section id="start" className="border-t" style={{ borderColor: 'var(--as-border)', background: 'color-mix(in oklch, var(--as-accent) 4%, transparent)' }}>
          <div className="mx-auto max-w-[840px] px-6 py-28 sm:px-8">
            <RevealBlock>
              <h2 className="text-center text-[clamp(1.6rem,4vw,2.4rem)] font-semibold tracking-tight" style={{ color: 'var(--as-text)' }}>
                Ready to run an experiment?
              </h2>
              <p className="mt-3 text-center text-[16px]" style={{ color: 'var(--as-text-3)' }}>
                Describe your ML problem in plain language. AutoSage does the rest.
              </p>
            </RevealBlock>

            <RevealBlock delay={0.15}>
              <div
                className="glass grain input-glow mt-10 rounded-3xl overflow-hidden transition-all focus-within:shadow-[0_0_0_2px_var(--as-accent),var(--as-glass-shadow)]"
                style={{ boxShadow: 'var(--as-glass-shadow)' }}
              >
                <div className="flex items-center gap-2 border-b px-5 py-3" style={{ borderColor: 'var(--as-border)' }}>
                  <motion.span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ background: 'var(--as-accent)' }}
                    animate={{ boxShadow: ['0 0 0px var(--as-accent-glow)', '0 0 10px var(--as-accent-glow)', '0 0 0px var(--as-accent-glow)'] }}
                    transition={{ repeat: Infinity, duration: 2 }}
                  />
                  <span className="mono text-[11.5px] tracking-[0.1em] uppercase" style={{ color: 'var(--as-text-3)' }}>new experiment</span>
                </div>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') void start() }}
                  rows={3}
                  spellCheck={false}
                  placeholder="Describe what you want AutoSage to build…"
                  className="w-full resize-none bg-transparent px-6 py-5 text-[17px] leading-relaxed outline-none"
                  style={{ color: 'var(--as-text)', caretColor: 'var(--as-accent)' }}
                />
                <div className="flex flex-wrap items-center justify-between gap-3 border-t px-5 py-3" style={{ borderColor: 'var(--as-border)' }}>
                  <button onClick={() => setPrompt(EXAMPLE)} className="mono max-w-full truncate text-left text-[12.5px] transition-colors hover:!text-[var(--as-text-2)]" style={{ color: 'var(--as-text-3)' }} title={EXAMPLE}>
                    e.g. "{EXAMPLE}"
                  </button>
                  <MagneticButton onClick={() => void start()} disabled={busy} className="btn-pill btn-primary text-[14.5px]" style={{ height: '36px' }}>
                    {busy ? 'Starting…' : 'Start Experiment'}
                    <ArrowRight size={13} />
                  </MagneticButton>
                </div>
              </div>
            </RevealBlock>

            <RevealBlock delay={0.2}>
              <p className="mono mt-5 text-center text-[12.5px]" style={{ color: 'var(--as-text-3)' }}>
                {STAGE_META.length} stages · JWT via /auth/dev-token · POST /experiments
              </p>
            </RevealBlock>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer className="border-t" style={{ borderColor: 'var(--as-border)' }}>
          <div className="mx-auto max-w-[1200px] px-6 pt-14 sm:px-8" aria-hidden>
            <SplitText
              text="AutoSage"
              tag="div"
              by="chars"
              className="text-center font-semibold leading-none tracking-tight select-none"
              style={{
                fontSize: 'clamp(4rem, 15vw, 11rem)',
                color: 'transparent',
                WebkitTextStroke: '1px var(--as-border-hi)',
              }}
            />
          </div>
          <RevealBlock>
            <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-6 py-8 sm:px-8">
              <div className="flex items-center gap-3">
                <Logo compact />
                <span className="text-[13.5px]" style={{ color: 'var(--as-text-3)' }}>Verified Multi-Agent AutoML</span>
              </div>
              <div className="flex items-center gap-4">
                <span className="mono text-[12.5px]" style={{ color: 'var(--as-text-3)' }}>
                  {authError ? 'auth error' : authReady ? 'engine online' : 'connecting…'}
                </span>
                {/* Back to top */}
                <motion.button
                  onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
                  className="btn-ghost btn-pill text-[13px]"
                  style={{ height: '32px', padding: '0 12px' }}
                  whileHover={{ y: -2 }}
                  whileTap={{ scale: 0.95 }}
                  aria-label="Back to top"
                >
                  ↑ Top
                </motion.button>
                <ThemeToggle />
              </div>
            </div>
          </RevealBlock>
        </footer>
      </div>
    </div>
  )
}
