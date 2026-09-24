import { useMemo, useState } from 'react'
import { ChevronRight, Search } from 'lucide-react'
import { PageHeader } from '../components/layout/Sidebar'
import { Badge } from '../components/ui/Badge'
import { statusTone } from '../lib/tones'
import { EmptyState } from '../components/ui/Primitives'
import { EVIDENCE } from '../data/evidence'
import type { VerificationStatus } from '../lib/types'

const FILTERS: ('ALL' | VerificationStatus)[] = ['ALL', 'VERIFIED', 'UNVERIFIED', 'CONFLICTING', 'QUARANTINED']

const COUNTS = (status: VerificationStatus) =>
  EVIDENCE.filter((c) => c.status === status).length

export function EvidencePage() {
  const [filter, setFilter] = useState<'ALL' | VerificationStatus>('ALL')
  const [q, setQ] = useState('')
  const [openId, setOpenId] = useState<string | null>('clm-4823')

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return EVIDENCE.filter((c) => filter === 'ALL' || c.status === filter).filter(
      (c) =>
        !needle ||
        c.claim.toLowerCase().includes(needle) ||
        c.source.toLowerCase().includes(needle) ||
        c.agent.toLowerCase().includes(needle) ||
        c.experiment.includes(needle),
    )
  }, [filter, q])

  return (
    <div className="flex h-full min-w-0 flex-col">
      <PageHeader
        title="Evidence"
        subtitle="Every claim emitted by an agent, with its source artifact, independent verification result and any conflicting observations. Quarantined claims never reach a final report."
        right={
          <div className="mono hidden shrink-0 text-right text-[13px] leading-relaxed text-paper-500 md:block">
            {EVIDENCE.length} claims indexed
            <br />
            {COUNTS('QUARANTINED')} quarantined · {COUNTS('CONFLICTING')} conflicting
          </div>
        }
      />

      <div className="flex flex-wrap items-center gap-2 border-b border-ink-600 bg-ink-900/70 px-5 py-2.5">
        <div className="relative">
          <Search size={12} className="absolute top-1/2 left-2 -translate-y-1/2 text-paper-500" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search claims, sources, agents…"
            className="h-[28px] w-[260px] rounded-sm border border-ink-600 bg-ink-850 pr-2 pl-7 text-[15px] text-paper-100 outline-none transition focus:border-accent-500"
          />
        </div>
        <div className="flex items-center gap-1">
          {FILTERS.map((f) => {
            const count = f === 'ALL' ? EVIDENCE.length : COUNTS(f)
            return (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`flex items-center gap-1.5 rounded-sm border px-2 py-[3px] text-[13px] tracking-[0.04em] transition ${
                  filter === f
                    ? 'border-ink-400 bg-ink-750 text-paper-50'
                    : 'border-ink-700 text-paper-400 hover:border-ink-500 hover:text-paper-200'
                }`}
              >
                {f}
                <span className="mono tnum text-[12px] text-paper-500">{count}</span>
              </button>
            )
          })}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {rows.length === 0 ? (
          <EmptyState
            title="No claims match this filter"
            detail="Adjust the status filter or clear the search query. Claims appear here as agents emit them during a run."
          />
        ) : (
          <ul className="divide-y divide-ink-700/70">
            {rows.map((c) => {
              const open = openId === c.id
              return (
                <li key={c.id} className={open ? 'bg-ink-850/50' : ''}>
                  <button
                    onClick={() => setOpenId(open ? null : c.id)}
                    className="flex w-full items-start gap-3 px-5 py-3 text-left transition hover:bg-ink-850/60"
                  >
                    <ChevronRight
                      size={13}
                      className={`mt-[3px] shrink-0 text-paper-500 transition-transform ${open ? 'rotate-90' : ''}`}
                    />
                    <Badge tone={statusTone(c.status)} className="mt-[1px] w-[86px] shrink-0 justify-center">
                      {c.status}
                    </Badge>
                    <div className="min-w-0 flex-1">
                      <p className="text-[15.5px] leading-snug text-paper-100">{c.claim}</p>
                      <div className="mono mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[12.5px] text-paper-500">
                        <span className="text-paper-400">{c.id}</span>
                        <span>agent: {c.agent}</span>
                        <span>exp: {c.experiment}</span>
                        <span className="truncate">src: {c.source}</span>
                        <span>{c.timestamp}</span>
                      </div>
                    </div>
                    <div className="hidden w-[112px] shrink-0 sm:block">
                      <div className="flex items-center justify-between">
                        <span className="text-[12px] tracking-[0.06em] text-paper-500 uppercase">confidence</span>
                        <span className="mono text-[13.5px] text-paper-200">{c.confidence.toFixed(2)}</span>
                      </div>
                      <div className="mt-1 h-[3px] overflow-hidden rounded-full bg-ink-700">
                        <div
                          className={`h-full ${c.confidence >= 0.8 ? 'bg-verify-500' : c.confidence >= 0.5 ? 'bg-warn-500' : 'bg-conflict-500'}`}
                          style={{ width: `${c.confidence * 100}%` }}
                        />
                      </div>
                    </div>
                  </button>

                  {open && (
                    <div className="anim-fade-in grid grid-cols-1 gap-4 border-t border-ink-700 bg-ink-900/60 px-5 py-3.5 lg:grid-cols-2">
                      <div>
                        <div className="label-xs mb-2">Supporting evidence</div>
                        <ul className="flex flex-col gap-1.5">
                          {c.supporting.map((s, i) => (
                            <li key={i} className="flex items-start gap-2 text-[14px] leading-relaxed text-paper-300">
                              <span className="mt-[6px] h-1 w-1 shrink-0 rounded-full bg-verify-500" />
                              {s}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <div className="label-xs mb-2">Conflicting evidence</div>
                        {c.conflicting && c.conflicting.length > 0 ? (
                          <ul className="flex flex-col gap-1.5">
                            {c.conflicting.map((s, i) => (
                              <li key={i} className="flex items-start gap-2 text-[14px] leading-relaxed text-paper-300">
                                <span className="mt-[6px] h-1 w-1 shrink-0 rounded-full bg-conflict-500" />
                                {s}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-[14px] text-paper-500">
                            None recorded. Independent recompute agreed with the agent output.
                          </p>
                        )}
                      </div>
                      <div className="border-t border-ink-700/70 pt-3 lg:col-span-2">
                        <div className="mono text-[13px] leading-relaxed text-paper-500">
                          source → {c.source}
                          <br />
                          recorded → {c.timestamp} · verifier=strict-recompute · bundle=evidence.bundle#{c.id}
                        </div>
                      </div>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
