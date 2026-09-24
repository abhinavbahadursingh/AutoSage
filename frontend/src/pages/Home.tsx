import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { Logo } from '../components/layout/Sidebar'
import { useStore } from '../store/context'

const PROCESS = ['Natural Language', 'Agent Reasoning', 'Experiment', 'Verification', 'Reproducible Pipeline']

const CONCEPTS = [
  {
    n: '01',
    title: 'UNDERSTAND',
    body: "AutoSage interprets the user's ML objective and dataset.",
  },
  {
    n: '02',
    title: 'EXPERIMENT',
    body: 'Specialized agents prepare data, select models, test approaches, and evaluate results.',
  },
  {
    n: '03',
    title: 'VERIFY',
    body: 'Important decisions are checked against evidence and recorded in an auditable trail.',
  },
]

const FOCUS = [
  'Evidence-backed decisions',
  'Independent verification',
  'Reproducible experiments',
  'Reusable experience from previous experiments',
]

const JOURNEY = [
  { n: '01', title: 'Describe your problem', note: 'Plain language, no DSL.' },
  { n: '02', title: 'AutoSage plans the experiment', note: 'A task graph of nine stages.' },
  { n: '03', title: 'Specialized agents execute it', note: 'Each agent owns one stage.' },
  { n: '04', title: 'Results are empirically tested', note: 'Cross-validation and holdout.' },
  { n: '05', title: 'Decisions are verified', note: 'Claims recomputed independently.' },
  { n: '06', title: 'A reproducible pipeline is produced', note: 'Seeded, signed, replayable.' },
]

const EXAMPLE = 'Predict customer churn from my dataset and optimize for recall.'

function SectionLabel({ index, title }: { index: string; title: string }) {
  return (
    <div className="mb-10 flex items-baseline gap-4">
      <span className="mono text-[13.5px] text-paper-500">{index}</span>
      <span className="h-px flex-1 bg-ink-700" />
      <span className="text-[13.5px] font-semibold tracking-[0.16em] text-paper-400 uppercase">{title}</span>
    </div>
  )
}

export function HomePage() {
  const navigate = useNavigate()
  const { createAndRun } = useStore()
  const [prompt, setPrompt] = useState('')

  const start = (text?: string) => {
    const body = (text ?? prompt).trim() || EXAMPLE
    createAndRun({
      prompt: body,
      dataset: 'telco_churn_2024.csv',
      target: 'churn',
      metric: 'recall',
      budget: '12 fit-min',
      verificationLevel: 'strict',
    })
    navigate('/workspace')
  }

  return (
    <div className="relative h-full w-full flex-1 overflow-y-auto">
      <div className="relative z-10">
      <header className="sticky top-0 z-30 border-b border-ink-700/80 bg-ink-900/95 backdrop-blur-[2px]">
        <div className="mx-auto flex h-[58px] max-w-[1180px] items-center justify-between px-8">
          <Logo />
          <div className="flex items-center gap-6">
            <span className="mono hidden text-[13px] text-paper-500 sm:block">
              8 agents available · verification engine online
            </span>
            <button
              onClick={() => start()}
              className="flex h-[30px] items-center gap-1.5 rounded-sm border border-ink-500 px-3 text-[15px] font-medium text-paper-100 transition hover:border-accent-500 hover:text-accent-300"
            >
              Start an Experiment
            </button>
          </div>
        </div>
      </header>

      {/* ── Hero ─────────────────────────────────────────── */}
      <section className="mx-auto grid max-w-[1180px] grid-cols-1 gap-16 px-8 pt-24 pb-28 lg:grid-cols-[1fr_280px] lg:gap-24">
        <div className="anim-rise">
          <div className="text-[15px] font-semibold tracking-[0.42em] text-paper-300 uppercase">Auto Sage</div>
          <div className="mt-2 text-[15px] tracking-[0.14em] text-accent-400 uppercase">Verified Multi-Agent AutoML</div>

          <h1 className="mt-10 max-w-[16ch] text-[49px] leading-[1.08] font-semibold tracking-[-0.03em] text-paper-50 sm:text-[60px]">
            From a question to a verified ML pipeline.
          </h1>

          <p className="mt-7 max-w-[62ch] text-[17.5px] leading-[1.75] text-paper-300">
            AutoSage turns natural-language machine learning tasks into reproducible experiments using specialized AI
            agents, empirical testing, and independent verification.
          </p>

          <div className="mt-10 flex flex-wrap items-center gap-3">
            <button
              onClick={() => start()}
              className="flex h-[40px] items-center gap-2 rounded-sm border border-accent-500 bg-accent-500 px-5 text-[16px] font-semibold text-ink-950 transition hover:bg-accent-400 hover:border-accent-400"
            >
              Start an Experiment <ArrowRight size={14} />
            </button>
            <a
              href="#how"
              className="flex h-[40px] items-center rounded-sm border border-ink-500 px-5 text-[16px] font-medium text-paper-200 transition hover:border-ink-400 hover:bg-ink-850"
            >
              Explore How It Works
            </a>
          </div>
        </div>

        {/* process column */}
        <ol className="relative hidden flex-col border-l border-ink-600 pl-8 lg:flex">
          <span className="anim-travel-y absolute -left-[3px] h-[5px] w-[5px] rounded-full bg-accent-400" />
          {PROCESS.map((step, i) => (
            <li key={step} className="relative py-[18px]">
              <span
                className={`absolute top-[26px] -left-[calc(2rem+3.5px)] h-[7px] w-[7px] rounded-full border ${
                  i === PROCESS.length - 1
                    ? 'border-accent-500 bg-accent-900'
                    : 'border-ink-400 bg-ink-900'
                }`}
              />
              <div className="mono text-[12px] tracking-[0.14em] text-paper-500">{`0${i + 1}`}</div>
              <div className={`mt-1 text-[16.5px] ${i === PROCESS.length - 1 ? 'text-paper-50' : 'text-paper-200'}`}>
                {step}
              </div>
            </li>
          ))}
        </ol>
      </section>

      {/* ── What is AutoSage ─────────────────────────────── */}
      <section className="border-t border-ink-700/80">
        <div className="mx-auto max-w-[1180px] px-8 py-24">
          <SectionLabel index="01" title="What is AutoSage?" />
          <div className="grid grid-cols-1 gap-y-12 md:grid-cols-3 md:gap-x-0">
            {CONCEPTS.map((c, i) => (
              <div
                key={c.title}
                className={`md:px-8 ${i === 0 ? 'md:pl-0' : 'md:border-l md:border-ink-700'} ${
                  i === CONCEPTS.length - 1 ? 'md:pr-0' : ''
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="mono text-[13.5px] text-accent-400">{c.n}</span>
                  <span className="h-px w-6 bg-ink-500" />
                  <span className="text-[15px] font-semibold tracking-[0.18em] text-paper-100">{c.title}</span>
                </div>
                <p className="mt-4 max-w-[34ch] text-[16.5px] leading-[1.75] text-paper-400">{c.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Why AutoSage ─────────────────────────────────── */}
      <section className="border-t border-ink-700/80 bg-ink-950/40">
        <div className="mx-auto max-w-[1180px] px-8 py-24">
          <SectionLabel index="02" title="Why AutoSage?" />
          <div className="grid grid-cols-1 gap-12 lg:grid-cols-[1.4fr_1fr] lg:gap-20">
            <p className="max-w-[54ch] text-[21.5px] leading-[1.7] font-light tracking-[-0.01em] text-paper-200">
              Traditional AutoML can automate model training, but users often cannot clearly understand{' '}
              <em className="text-paper-50 not-italic">why</em> a pipeline was selected or whether an AI-generated
              decision is trustworthy.
            </p>
            <ul className="flex flex-col gap-0">
              {FOCUS.map((f, i) => (
                <li
                  key={f}
                  className="flex items-baseline gap-4 border-b border-ink-700 py-3.5 first:border-t first:border-ink-700"
                >
                  <span className="mono text-[12.5px] text-paper-500">{`0${i + 1}`}</span>
                  <span className="text-[16.5px] text-paper-200">{f}</span>
                  <span className="ml-auto h-1.5 w-1.5 shrink-0 translate-y-[-1px] rounded-full bg-accent-500/70" />
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────── */}
      <section id="how" className="scroll-mt-20 border-t border-ink-700/80">
        <div className="mx-auto max-w-[1180px] px-8 py-24">
          <SectionLabel index="03" title="How it works" />
          <div className="relative">
            <div className="absolute top-[7px] right-0 left-0 hidden h-px bg-ink-700 md:block">
              <span className="anim-travel-x absolute -top-[2px] h-[5px] w-[5px] rounded-full bg-accent-400" />
            </div>
            <ol className="grid grid-cols-1 gap-x-6 gap-y-9 sm:grid-cols-2 lg:grid-cols-6">
              {JOURNEY.map((s, i) => (
                <li key={s.n} className="anim-rise relative" style={{ animationDelay: `${i * 90}ms` }}>
                  <span className="relative z-10 block h-[15px] w-[15px] rounded-full border border-ink-400 bg-ink-900">
                    <span className="absolute inset-[4px] rounded-full bg-ink-500 transition-colors" />
                  </span>
                  <div className="mono mt-5 text-[13px] tracking-[0.12em] text-accent-400">{s.n}</div>
                  <h3 className="mt-2 text-[16.5px] leading-snug font-medium text-paper-100">{s.title}</h3>
                  <p className="mt-1.5 text-[15px] leading-relaxed text-paper-500">{s.note}</p>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      {/* ── Evidence + Memory ────────────────────────────── */}
      <section className="border-t border-ink-700/80">
        <div className="mx-auto max-w-[1180px] px-8 py-24">
          <SectionLabel index="04" title="Research concepts" />
          <div className="grid grid-cols-1 gap-12 lg:grid-cols-2 lg:gap-0">
            <article className="lg:pr-16">
              <div className="mono text-[13px] tracking-[0.14em] text-paper-500 uppercase">Concept A</div>
              <h3 className="mt-3 text-[24px] font-medium tracking-[-0.015em] text-paper-50">
                Evidence &amp; Reasoning Trail
              </h3>
              <p className="mt-4 border-l border-accent-600/60 pl-4 text-[18.5px] leading-[1.7] text-paper-300 italic">
                “Every important decision leaves an inspectable trail.”
              </p>
              <p className="mt-4 max-w-[46ch] text-[16px] leading-[1.75] text-paper-500">
                Claims, their sources, and the result of independent recomputation are stored together — including
                conflicts, which are quarantined rather than hidden.
              </p>
            </article>
            <article className="border-t border-ink-700 pt-12 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-16">
              <div className="mono text-[13px] tracking-[0.14em] text-paper-500 uppercase">Concept B</div>
              <h3 className="mt-3 text-[24px] font-medium tracking-[-0.015em] text-paper-50">Experience Memory</h3>
              <p className="mt-4 border-l border-accent-600/60 pl-4 text-[18.5px] leading-[1.7] text-paper-300 italic">
                “Verified experience from previous experiments can inform future ones.”
              </p>
              <p className="mt-4 max-w-[46ch] text-[16px] leading-[1.75] text-paper-500">
                What worked, what failed, and why a prior run is trustworthy — searchable before a new experiment
                starts, so agents plan from evidence instead of guesses.
              </p>
            </article>
          </div>
        </div>
      </section>

      {/* ── Start experiment ─────────────────────────────── */}
      <section id="start" className="border-t border-ink-700/80 bg-ink-950/50">
        <div className="mx-auto max-w-[860px] px-8 py-28">
          <h2 className="text-center text-[31px] font-semibold tracking-[-0.02em] text-paper-50">
            Ready to run an experiment?
          </h2>

          <div className="mt-10 rounded-md border border-ink-500 bg-ink-900 transition focus-within:border-accent-500">
            <div className="flex items-center gap-2 border-b border-ink-700 px-4 py-2">
              <span className="h-1.5 w-1.5 rounded-full bg-accent-400" />
              <span className="mono text-[12.5px] tracking-[0.1em] text-paper-500 uppercase">new experiment</span>
            </div>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') start()
              }}
              rows={3}
              spellCheck={false}
              placeholder="Describe what you want AutoSage to build…"
              className="w-full resize-none bg-transparent px-5 py-5 text-[18.5px] leading-relaxed text-paper-50 outline-none placeholder:text-paper-500"
            />
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-ink-700 px-4 py-3">
              <button
                onClick={() => setPrompt(EXAMPLE)}
                className="mono max-w-full truncate text-left text-[13.5px] text-paper-500 transition hover:text-paper-300"
                title={EXAMPLE}
              >
                e.g. “{EXAMPLE}”
              </button>
              <button
                onClick={() => start()}
                className="flex h-[34px] shrink-0 items-center gap-2 rounded-sm border border-accent-500 bg-accent-500 px-4 text-[15.5px] font-semibold text-ink-950 transition hover:border-accent-400 hover:bg-accent-400"
              >
                Start Experiment <ArrowRight size={13} />
              </button>
            </div>
          </div>

          <p className="mono mt-4 text-center text-[13px] text-paper-500">
            9 stages · 8 agents · strict verification
          </p>
        </div>
      </section>

      <footer className="border-t border-ink-700/80">
        <div className="mx-auto flex max-w-[1180px] flex-wrap items-center justify-between gap-4 px-8 py-8">
          <div className="flex items-center gap-3">
            <Logo compact />
            <span className="text-[14px] text-paper-500">Verified Multi-Agent AutoML</span>
          </div>
          <span className="mono text-[13px] text-paper-500">v0.9.4 · engine online · 8 agents available</span>
        </div>
      </footer>
      </div>
    </div>
  )
}
