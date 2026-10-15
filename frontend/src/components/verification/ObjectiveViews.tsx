/**
 * Shared presentation for Objective Verification results.
 *
 * Extracted so the three pages that show verification evidence — Objectives
 * (overview), Evidence (detail) and any future consumer — render the same
 * verdicts the same way. Status semantics, evidence categories and
 * verification levels live here exactly once; they must not be re-invented
 * per page or the honest-status guarantees drift.
 *
 * Nothing in this module fabricates data: every component renders only the
 * fields it is given, and says "not stated"/"not verified" where a record is
 * genuinely absent.
 */
import { useState } from 'react'
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ChevronRight,
  CircleSlash,
  Info,
  Loader2,
  XCircle,
} from 'lucide-react'

import type {
  ObjectiveCheckResult,
  ObjectiveCheckStatus,
  ObjectiveDesignRecord,
} from '../../lib/api'

export type StageState =
  | 'PENDING'
  | 'RUNNING'
  | 'PASSED'
  | 'FAILED'
  | 'NOT_VERIFIED'
  | 'BLOCKED'

export const CHECK_META: Record<
  ObjectiveCheckStatus,
  { label: string; color: string; bg: string; Icon: typeof CheckCircle2 }
> = {
  PASS: {
    label: 'PASS',
    color: 'var(--as-verify)',
    bg: 'color-mix(in oklch, var(--as-verify) 14%, transparent)',
    Icon: CheckCircle2,
  },
  FAIL: {
    label: 'FAIL',
    color: 'var(--as-error)',
    bg: 'color-mix(in oklch, var(--as-error) 14%, transparent)',
    Icon: XCircle,
  },
  NOT_VERIFIED: {
    label: 'NOT VERIFIED',
    color: 'var(--as-warn)',
    bg: 'color-mix(in oklch, var(--as-warn) 14%, transparent)',
    Icon: CircleSlash,
  },
  BLOCKED: {
    label: 'BLOCKED',
    color: 'var(--as-text-3)',
    bg: 'color-mix(in oklch, var(--as-text-3) 12%, transparent)',
    Icon: Ban,
  },
}

export const STAGE_META: Record<
  StageState,
  { label: string; color: string; Icon: typeof CheckCircle2 }
> = {
  PENDING: { label: 'Pending', color: 'var(--as-text-3)', Icon: CircleSlash },
  RUNNING: { label: 'Running', color: 'var(--as-accent)', Icon: Loader2 },
  PASSED: { label: 'Passed', color: 'var(--as-verify)', Icon: CheckCircle2 },
  FAILED: { label: 'Failed', color: 'var(--as-error)', Icon: XCircle },
  NOT_VERIFIED: { label: 'Not verified', color: 'var(--as-warn)', Icon: CircleSlash },
  BLOCKED: { label: 'Blocked', color: 'var(--as-text-3)', Icon: Ban },
}

/**
 * What kind of evidence a check examined. Kept deliberately separate from the
 * verdict: a repository-level PASS shows a capability exists in source, not
 * that a specific generated decision is correct.
 */
export const CATEGORY_META: Record<string, { label: string; hint: string }> = {
  source: {
    label: 'repository',
    hint: 'Read from repository source. Proves the capability exists in code — not that any particular generated decision is right.',
  },
  probe: {
    label: 'synthetic probe',
    hint: 'A pure helper called with synthetic in-memory data. No real dataset was read.',
  },
  session: {
    label: 'this session',
    hint: "Read from this session's own database records. A fresh session has none until something actually runs.",
  },
  generated: {
    label: 'generated code',
    hint: 'Inspected in generated code, which this workflow never executes automatically.',
  },
  empirical: {
    label: 'empirical',
    hint: 'Measured from a real executed run.',
  },
}

export const LEVEL_META: Record<string, { label: string; color: string }> = {
  source: { label: 'source-level', color: 'var(--as-teal)' },
  config: { label: 'config-level', color: 'var(--as-accent)' },
  generated: { label: 'generated-level', color: 'var(--as-warn)' },
  runtime: { label: 'runtime-level', color: 'var(--as-error)' },
}

export function CategoryTag({ category }: { category?: string }) {
  if (!category) return null
  const meta = CATEGORY_META[category]
  if (!meta) return null
  return (
    <span
      className="mono shrink-0 rounded border px-1 py-[1px] text-[9.5px] uppercase tracking-wider"
      style={{
        borderColor: 'var(--as-border-hi)',
        color: 'var(--as-text-3)',
        background: 'var(--as-bg-2)',
      }}
      title={meta.hint}
    >
      {meta.label}
    </span>
  )
}

export function CheckPill({ status, small = false }: { status: ObjectiveCheckStatus; small?: boolean }) {
  const meta = CHECK_META[status]
  const { Icon } = meta
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded-full border font-semibold uppercase tracking-wider ${
        small ? 'px-1.5 py-[1px] text-[9.5px]' : 'px-2 py-0.5 text-[10.5px]'
      }`}
      style={{
        color: meta.color,
        background: meta.bg,
        borderColor: `color-mix(in oklch, ${meta.color} 34%, transparent)`,
      }}
      title={meta.label}
    >
      <Icon size={small ? 9 : 11} />
      {meta.label}
    </span>
  )
}

export function stamp(value: string | null | undefined): string {
  if (!value) return '--:--:--'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleTimeString(undefined, { hour12: false })
}

/**
 * A confidence value drawn as a measurement: the filled span is the value,
 * the number sits beside it in the mono face. A missing confidence is stated,
 * never drawn as an empty or full bar.
 */
export function ConfidenceMeter({
  value,
  color,
  width = 84,
  animated = false,
  showValue = true,
}: {
  value: number | null | undefined
  color: string
  width?: number
  animated?: boolean
  /** Off when the value is already set large beside the meter. */
  showValue?: boolean
}) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return (
      <span className="mono text-[11.5px]" style={{ color: 'var(--as-text-3)' }}>
        not stated
      </span>
    )
  }
  const pct = Math.max(0, Math.min(1, value))
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className="inline-block h-[3px] shrink-0 overflow-hidden rounded-full"
        style={{ width, background: 'var(--as-border)' }}
        role="presentation"
      >
        <span
          className={`block h-full rounded-full ${animated ? 'anim-bar' : ''}`}
          style={{ width: `${pct * 100}%`, background: color }}
        />
      </span>
      {showValue && (
        <span className="mono tnum text-[11.5px]" style={{ color: 'var(--as-text-2)' }}>
          {Math.round(pct * 100)}%
        </span>
      )}
    </span>
  )
}

/**
 * One check's full record: verdict, evidence kind and strength, the
 * expected/actual pair, the verbatim evidence lines, and — for anything not
 * verified — an explicit missing-evidence callout. This is the detailed audit
 * view; the Objectives page keeps only pills and dots.
 */
export function DecisionCard({ check }: { check: ObjectiveCheckResult }) {
  const [open, setOpen] = useState(false)
  const hasDetail =
    check.evidence.length > 0 || !!check.actual || !!check.expected || !!check.artifact
  const meta = CHECK_META[check.status]
  const { Icon } = meta
  const level = check.verification_level ? LEVEL_META[check.verification_level] : undefined
  const category = check.category ? CATEGORY_META[check.category] : undefined
  // A source/config/generated PASS is weaker evidence than a runtime one and
  // the card must say so rather than let the green pill imply otherwise.
  const weakPass =
    check.status === 'PASS' && !!level && check.verification_level !== 'runtime'

  return (
    <div className="border-b last:border-b-0" style={{ borderColor: 'var(--as-border)' }}>
      <button
        type="button"
        onClick={() => hasDetail && setOpen((v) => !v)}
        className="flex w-full items-center gap-2.5 px-4 py-2.5 text-left transition-colors hover:bg-[color-mix(in_oklch,var(--as-accent)_7%,transparent)]"
        aria-expanded={hasDetail ? open : undefined}
      >
        <Icon size={13} style={{ color: meta.color }} className="shrink-0" />
        <span className="min-w-0 flex-1 truncate text-[13px]" style={{ color: 'var(--as-text)' }}>
          {check.title}
        </span>
        <CategoryTag category={check.category} />
        <CheckPill status={check.status} small />
        {hasDetail && (
          <ChevronRight
            size={13}
            className={`shrink-0 transition-transform ${open ? 'rotate-90' : ''}`}
            style={{ color: 'var(--as-text-3)' }}
          />
        )}
      </button>

      {open && hasDetail && (
        <div
          className="space-y-2 px-4 pb-3 pl-8 text-[12px] leading-relaxed"
          style={{ color: 'var(--as-text-2)' }}
        >
          {check.expected && (
            <p>
              <span className="label-xs mr-1" style={{ color: 'var(--as-text-3)' }}>
                Expected
              </span>
              {check.expected}
            </p>
          )}
          {check.actual && (
            <p>
              <span className="label-xs mr-1" style={{ color: 'var(--as-text-3)' }}>
                Actual
              </span>
              <span style={{ color: meta.color }}>{check.actual}</span>
            </p>
          )}

          {/* Evidence kind + strength, so the verdict is read in proportion */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
            {category && (
              <span style={{ color: 'var(--as-text-3)' }}>
                Evidence: <span style={{ color: 'var(--as-text-2)' }}>{category.label}</span>
              </span>
            )}
            {level && (
              <span style={{ color: 'var(--as-text-3)' }}>
                Level:{' '}
                <span className="mono" style={{ color: level.color }}>
                  {level.label}
                </span>
              </span>
            )}
          </div>
          {category && (
            <p className="text-[11.5px] italic" style={{ color: 'var(--as-text-3)' }}>
              {category.hint}
            </p>
          )}
          {weakPass && (
            <div
              className="flex items-start gap-2 rounded-md border px-2.5 py-2 text-[11.5px]"
              style={{
                borderColor: 'color-mix(in oklch, var(--as-teal) 25%, transparent)',
                background: 'color-mix(in oklch, var(--as-teal) 6%, transparent)',
                color: 'var(--as-teal)',
              }}
            >
              <Info size={12} className="mt-0.5 shrink-0" />
              <span>
                This pass is {level?.label} evidence. It confirms the capability is present —
                it does not prove that any specific generated decision is correct, and nothing
                here was executed.
              </span>
            </div>
          )}

          {/* Decision trail: confidence, artifact, timestamp */}
          <div
            className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px]"
            style={{ color: 'var(--as-text-3)' }}
          >
            <span>
              Confidence{' '}
              <span className="mono" style={{ color: 'var(--as-text-2)' }}>
                {(check.confidence * 100).toFixed(0)}%
              </span>
            </span>
            {check.artifact && (
              <span>
                Source <span className="mono" style={{ color: 'var(--as-teal)' }}>{check.artifact}</span>
              </span>
            )}
            <span>
              Checked <span className="mono">{stamp(check.checked_at)}</span>
            </span>
          </div>

          {/* Evidence references */}
          {check.evidence.length > 0 && (
            <div>
              <div className="label-xs mb-1" style={{ color: 'var(--as-text-3)' }}>
                Evidence
              </div>
              <ul
                className="mono space-y-0.5 rounded-md px-2.5 py-2 text-[11px]"
                style={{ background: 'var(--as-bg)', color: 'var(--as-text-2)' }}
              >
                {check.evidence.map((line, i) => (
                  <li key={i} className="flex gap-1.5">
                    <span style={{ color: 'var(--as-teal)' }}>›</span>
                    <span className="min-w-0 break-words">{line}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Missing evidence callout */}
          {check.status === 'NOT_VERIFIED' && check.evidence.length > 0 && (
            <div
              className="flex items-start gap-2 rounded-md border px-2.5 py-2 text-[11.5px]"
              style={{
                borderColor: 'color-mix(in oklch, var(--as-warn) 25%, transparent)',
                background: 'color-mix(in oklch, var(--as-warn) 6%, transparent)',
                color: 'var(--as-warn)',
              }}
            >
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              <span>
                This check could not be fully verified. The evidence above shows what was
                found and what is missing. This is not a pass.
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function KeyValue({ k, v }: { k: string; v: unknown }) {
  return (
    <li className="flex gap-2 break-inside-avoid">
      <span className="mono shrink-0" style={{ color: 'var(--as-teal)' }}>
        {k}
      </span>
      <span className="min-w-0 break-words" style={{ color: 'var(--as-text-2)' }}>
        {typeof v === 'string' ? v : JSON.stringify(v)}
      </span>
    </li>
  )
}

function Cell({
  label,
  className = '',
  children,
}: {
  label: string
  className?: string
  children: React.ReactNode
}) {
  return (
    <div
      className={`min-w-0 px-4 py-3.5 ${className}`}
      style={{ borderColor: 'var(--as-border)' }}
    >
      <div className="label-xs">{label}</div>
      <div className="mt-1.5">{children}</div>
    </div>
  )
}

/**
 * The decisions behind the generated code: algorithm, hyperparameters,
 * metrics, validation strategy, assumptions and alternatives, each with its
 * rationale/confidence/source *only when the model actually produced one*.
 */
export function DecisionExplorer({ design }: { design: ObjectiveDesignRecord | null }) {
  const [openId, setOpenId] = useState<number | null>(null)

  if (!design) return null
  const decisions = design.decisions ?? []
  const hp = design.hyperparameters ?? {}
  const metrics = design.metrics ?? {}
  const assumptions = design.assumptions ?? []
  const alternatives = design.alternatives ?? []
  // More than one alternative flows into two parallel columns so the cell
  // grows sideways instead of down. A single item has nothing to divide, and
  // halving its width would only make it wrap taller.
  const altTwoColumns = alternatives.length >= 2
  const hasAnything =
    design.algorithm ||
    design.validation_strategy ||
    Object.keys(hp).length > 0 ||
    Object.keys(metrics).length > 0 ||
    assumptions.length > 0 ||
    alternatives.length > 0 ||
    decisions.length > 0

  if (!hasAnything) return null

  return (
    <section className="px-4 py-5">
      <div className="flex items-baseline justify-between gap-3">
        <h3
          className="text-[15px] font-semibold tracking-tight"
          style={{ color: 'var(--as-text)' }}
        >
          Design Decisions
        </h3>
        <span className="mono text-[11px]" style={{ color: 'var(--as-text-3)' }}>
          {decisions.length} decision(s)
        </span>
      </div>

      {/* The design summary as one spec sheet: framed, divided, so a short
          cell reads as a table cell instead of a card with a hole under it. */}
      <div
        className="mt-3 overflow-hidden rounded-2xl border"
        style={{ borderColor: 'var(--as-border)', background: 'var(--as-bg-2)' }}
      >
        <div className="grid sm:grid-cols-2">
          <Cell label="Algorithm">
            <span
              className="break-words text-[15px] font-semibold tracking-tight"
              style={{ color: 'var(--as-text)' }}
            >
              {design.algorithm || <span style={{ color: 'var(--as-text-3)' }}>not stated</span>}
            </span>
          </Cell>
          <Cell label="Validation strategy" className="border-t sm:border-t-0 sm:border-l">
            <span
              className="break-words text-[15px] font-semibold tracking-tight"
              style={{ color: 'var(--as-text)' }}
            >
              {design.validation_strategy || (
                <span style={{ color: 'var(--as-text-3)' }}>not stated</span>
              )}
            </span>
          </Cell>
        </div>

        {(Object.keys(metrics).length > 0 || Object.keys(hp).length > 0) && (
          <div className="border-t" style={{ borderColor: 'var(--as-border)' }}>
            <div className="grid sm:grid-cols-2">
              {Object.keys(metrics).length > 0 && (
                <Cell
                  label="Metrics"
                  className={Object.keys(hp).length > 0 ? '' : 'sm:col-span-2'}
                >
                  <ul className="mono space-y-1 text-[11.5px]">
                    {Object.entries(metrics).map(([k, v]) => (
                      <KeyValue key={k} k={k} v={v} />
                    ))}
                  </ul>
                </Cell>
              )}
              {Object.keys(hp).length > 0 && (
                <Cell
                  label="Hyperparameters"
                  className={
                    Object.keys(metrics).length > 0 ? 'border-t sm:border-t-0 sm:border-l' : ''
                  }
                >
                  {/* Two parallel columns: the longest cell in the sheet, halved. */}
                  <ul className="mono sm:columns-2 sm:gap-x-5 space-y-1 text-[11.5px]">
                    {Object.entries(hp).map(([k, v]) => (
                      <KeyValue key={k} k={k} v={v} />
                    ))}
                  </ul>
                </Cell>
              )}
            </div>
          </div>
        )}

        {(assumptions.length > 0 || alternatives.length > 0) && (
          <div className="border-t" style={{ borderColor: 'var(--as-border)' }}>
            <div className="grid sm:grid-cols-2">
              {assumptions.length > 0 && (
                <Cell
                  label="Assumptions"
                  className={alternatives.length > 0 ? '' : 'sm:col-span-2'}
                >
                  <ul className="space-y-1 text-[12px]" style={{ color: 'var(--as-text-2)' }}>
                    {assumptions.map((a, i) => (
                      <li key={i} className="flex gap-1.5">
                        <span style={{ color: 'var(--as-warn)' }}>•</span>
                        <span className="min-w-0 break-words">{a}</span>
                      </li>
                    ))}
                  </ul>
                </Cell>
              )}
              {alternatives.length > 0 && (
                <Cell
                  label="Alternatives considered"
                  className={assumptions.length > 0 ? 'border-t sm:border-t-0 sm:border-l' : ''}
                >
                  <ul
                    className={
                      altTwoColumns
                        ? 'sm:columns-2 sm:gap-x-5 text-[12px] space-y-1'
                        : 'space-y-1 text-[12px]'
                    }
                    style={{ color: 'var(--as-text-2)' }}
                  >
                    {alternatives.map((a, i) => (
                      <li
                        key={i}
                        className={altTwoColumns ? 'flex gap-1.5 break-inside-avoid pb-1' : 'flex gap-1.5'}
                      >
                        <span style={{ color: 'var(--as-teal)' }}>×</span>
                        <span className="min-w-0 break-words">{a}</span>
                      </li>
                    ))}
                  </ul>
                </Cell>
              )}
            </div>
          </div>
        )}
      </div>

      {decisions.length > 0 && (
        <div
          className="mt-3 overflow-hidden rounded-2xl border"
          style={{ borderColor: 'var(--as-border)', background: 'var(--as-bg-2)' }}
        >
          {decisions.map((d, i) => {
            const open = openId === i
            return (
              <div
                key={i}
                className="border-b last:border-b-0"
                style={{
                  borderColor: 'var(--as-border)',
                  background: i % 2 ? 'color-mix(in oklch, var(--as-accent) 5%, transparent)' : 'transparent',
                }}
              >
                <button
                  type="button"
                  onClick={() => setOpenId(open ? null : i)}
                  className="flex w-full items-center gap-2.5 px-4 py-2.5 text-left transition-colors hover:bg-[color-mix(in_oklch,var(--as-accent)_7%,transparent)]"
                  aria-expanded={open}
                >
                  <span
                    className="mono shrink-0 rounded border px-1.5 py-[1px] text-[9.5px] uppercase tracking-wider"
                    style={{ borderColor: 'var(--as-border-hi)', color: 'var(--as-text-3)' }}
                  >
                    {d.category}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[13px]" style={{ color: 'var(--as-text)' }}>
                    {d.decision}
                  </span>
                  <span className="hidden shrink-0 md:block">
                    <ConfidenceMeter value={d.confidence} color="var(--as-accent)" width={52} />
                  </span>
                  <ChevronRight
                    size={13}
                    className={`shrink-0 transition-transform ${open ? 'rotate-90' : ''}`}
                    style={{ color: 'var(--as-text-3)' }}
                  />
                </button>

                {open && (
                  <div
                    className="space-y-2 px-4 pb-3 pl-8 text-[12px] leading-relaxed"
                    style={{ color: 'var(--as-text-2)' }}
                  >
                    {d.rationale ? (
                      <p>
                        <span className="label-xs mr-1" style={{ color: 'var(--as-text-3)' }}>
                          Why
                        </span>
                        {d.rationale}
                      </p>
                    ) : (
                      <p style={{ color: 'var(--as-text-3)' }}>
                        <span className="label-xs mr-1">Why</span>
                        not stated by the model — no rationale is invented here.
                      </p>
                    )}

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px]">
                      {typeof d.confidence === 'number' ? (
                        <span style={{ color: 'var(--as-text-3)' }}>
                          Confidence{' '}
                          <span className="mono" style={{ color: 'var(--as-text-2)' }}>
                            {(d.confidence * 100).toFixed(0)}%
                          </span>
                        </span>
                      ) : (
                        <span style={{ color: 'var(--as-text-3)' }}>
                          Confidence <span className="mono">not stated</span>
                        </span>
                      )}
                      {d.source && (
                        <span style={{ color: 'var(--as-text-3)' }}>
                          Source{' '}
                          <span className="mono" style={{ color: 'var(--as-teal)' }}>
                            {d.source}
                          </span>
                        </span>
                      )}
                    </div>

                    {(d.alternatives ?? []).length > 0 && (
                      <div>
                        <div className="label-xs mb-1" style={{ color: 'var(--as-text-3)' }}>
                          Alternatives rejected
                        </div>
                        <ul className="space-y-0.5 text-[12px]">
                          {(d.alternatives ?? []).map((a, j) => (
                            <li key={j} className="flex gap-1.5">
                              <span style={{ color: 'var(--as-teal)' }}>×</span>
                              <span className="min-w-0 break-words">{a}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {(d.assumptions ?? []).length > 0 && (
                      <div>
                        <div className="label-xs mb-1" style={{ color: 'var(--as-text-3)' }}>
                          Assumptions
                        </div>
                        <ul className="space-y-0.5 text-[12px]">
                          {(d.assumptions ?? []).map((a, j) => (
                            <li key={j} className="flex gap-1.5">
                              <span style={{ color: 'var(--as-warn)' }}>•</span>
                              <span className="min-w-0 break-words">{a}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <p className="mt-3 text-[12px] leading-relaxed" style={{ color: 'var(--as-text-2)' }}>
        Design-time decisions produced with the generated code. Nothing here was trained,
        executed or verified — these records explain the design, they do not prove it works.
      </p>
    </section>
  )
}
