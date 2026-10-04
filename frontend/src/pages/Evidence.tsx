import { useEffect, useState } from 'react'
import { PageHeader } from '../components/layout/Sidebar'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/Primitives'
import { api, ApiError, type EvidenceSourceInfo, type VerificationResponse } from '../lib/api'
import { useStore } from '../store/context'

export function EvidencePage() {
  const { activeExperiment, toast } = useStore()
  const [sources, setSources] = useState<EvidenceSourceInfo[] | null>(null)
  const [sourcesError, setSourcesError] = useState<string | null>(null)
  const [verifyRes, setVerifyRes] = useState<VerificationResponse | null>(null)
  const [verifyError, setVerifyError] = useState<string | null>(null)
  const [verifyBusy, setVerifyBusy] = useState(false)
  const [loadingSources, setLoadingSources] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoadingSources(true)
      try {
        const list = await api.listEvidenceSources()
        if (!cancelled) {
          setSources(list)
          setSourcesError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setSourcesError(err instanceof ApiError ? err.message : 'Failed to load verification sources')
          setSources([])
        }
      } finally {
        if (!cancelled) setLoadingSources(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const runVerify = async () => {
    if (!activeExperiment) return
    setVerifyBusy(true)
    setVerifyError(null)
    try {
      const res = await api.verifyExperiment(activeExperiment.id)
      setVerifyRes(res)
      toast({
        title: 'Verification complete',
        detail: `${res.verified_count}/${res.total_claims} verified · ${res.overall_status}`,
        tone: res.conflict_count > 0 ? 'warn' : 'success',
      })
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Verification request failed'
      setVerifyError(msg)
      setVerifyRes(null)
      toast({ title: 'Verification failed', detail: msg, tone: 'error' })
    } finally {
      setVerifyBusy(false)
    }
  }

  return (
    <div className="flex h-full min-w-0 flex-col">
      <PageHeader
        title="Evidence"
        subtitle="Independent verification of experiment claims. Sources come from GET /verification/sources; run a verification against the open experiment via POST /verification/experiment."
        right={
          <button
            onClick={() => void runVerify()}
            disabled={!activeExperiment || verifyBusy}
            className="flex h-[28px] items-center gap-1.5 rounded-sm border border-accent-500 bg-accent-500 px-2.5 text-[14px] font-medium text-ink-950 transition hover:bg-accent-400 disabled:cursor-not-allowed disabled:border-ink-600 disabled:bg-ink-750 disabled:text-paper-500"
            title={activeExperiment ? `Verify ${activeExperiment.id}` : 'Open an experiment first'}
          >
            {verifyBusy ? 'Verifying…' : 'Verify open experiment'}
          </button>
        }
      />

      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        <div className="grid max-w-[1100px] gap-4 lg:grid-cols-2">
          <section className="overflow-hidden rounded-md border border-ink-600 bg-ink-900">
            <div className="flex items-center justify-between border-b border-ink-600 px-4 py-2.5">
              <h3 className="label-xs text-paper-300">Verification sources</h3>
              <span className="mono text-[12.5px] text-paper-500">GET /verification/sources</span>
            </div>
            {loadingSources ? (
              <EmptyState title="Loading sources…" />
            ) : sourcesError ? (
              <EmptyState title="Could not load sources" detail={sourcesError} />
            ) : !sources || sources.length === 0 ? (
              <EmptyState title="No verification sources registered" detail="Backend returned an empty list." />
            ) : (
              <ul className="divide-y divide-ink-700/70">
                {sources.map((s) => (
                  <li key={s.source_id} className="flex items-center gap-3 px-4 py-3">
                    <Badge tone={s.credibility_score >= 0.8 ? 'verify' : s.credibility_score >= 0.5 ? 'warn' : 'conflict'}>
                      {s.source_type}
                    </Badge>
                    <div className="min-w-0 flex-1">
                      <div className="mono truncate text-[14px] text-paper-100">{s.source_id}</div>
                      <div className="mono text-[12.5px] text-paper-500">
                        credibility {s.credibility_score.toFixed(2)}
                        {s.last_updated ? ` · updated ${s.last_updated.slice(0, 10)}` : ''}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="overflow-hidden rounded-md border border-ink-600 bg-ink-900">
            <div className="flex items-center justify-between border-b border-ink-600 px-4 py-2.5">
              <h3 className="label-xs text-paper-300">Experiment verification</h3>
              <span className="mono text-[12.5px] text-paper-500">POST /verification/experiment</span>
            </div>
            {!activeExperiment ? (
              <EmptyState title="No experiment open" detail="Open an experiment from the Experiments list first." />
            ) : verifyError ? (
              <EmptyState title="Verification unavailable" detail={verifyError} />
            ) : !verifyRes ? (
              <EmptyState
                title="Not verified yet"
                detail={`Open experiment: ${activeExperiment.id.slice(0, 8)}… (${activeExperiment.status}). Click “Verify open experiment” to request independent recompute of claims.`}
              />
            ) : (
              <div className="p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={verifyRes.overall_status === 'VERIFIED' ? 'verify' : verifyRes.overall_status === 'CONFLICT' ? 'conflict' : verifyRes.overall_status === 'ABSTAIN' ? 'dim' : 'warn'}>
                    {verifyRes.overall_status}
                  </Badge>
                  <span className="mono text-[13px] text-paper-400">
                    {verifyRes.verified_count}/{verifyRes.total_claims} verified · conf{' '}
                    {verifyRes.overall_confidence.toFixed(2)}
                  </span>
                </div>
                <ul className="mt-3 flex flex-col gap-2">
                  {verifyRes.results.map((r) => (
                    <li key={r.claim_id} className="rounded-sm border border-ink-700 bg-ink-850/70 px-3 py-2.5">
                      <div className="flex items-start gap-2">
                        <Badge tone={r.status === 'VERIFIED' ? 'verify' : r.status === 'CONFLICT' ? 'conflict' : r.status === 'ABSTAIN' ? 'dim' : 'warn'}>
                          {r.status}
                        </Badge>
                        <p className="min-w-0 flex-1 text-[14.5px] leading-snug text-paper-200">{r.claim_text}</p>
                      </div>
                      <p className="mono mt-1.5 text-[12.5px] text-paper-500">
                        {r.claim_id} · conf {r.confidence_score.toFixed(2)} · supporting{' '}
                        {r.supporting_evidence.length} · contradicting {r.contradicting_evidence.length}
                      </p>
                      {r.reasoning && (
                        <p className="mt-1.5 text-[13.5px] leading-relaxed text-paper-400">{r.reasoning}</p>
                      )}
                      {r.status === 'ABSTAIN' && !r.reasoning && (
                        <p className="mt-1.5 text-[12px] text-paper-400">⚠️ Abstained: low confidence / unreliable evidence</p>
                      )}
                    </li>
                  ))}
                  {verifyRes.results.length === 0 && (
                    <li className="text-[14px] text-paper-500">No claims returned for this experiment.</li>
                  )}
                </ul>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
