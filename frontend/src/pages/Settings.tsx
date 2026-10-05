import { useState } from 'react'
import { PageHeader } from '../components/layout/Sidebar'
import { Badge } from '../components/ui/Badge'
import { SectionTitle } from '../components/ui/Primitives'
import { isDevTokenAllowed } from '../lib/api'
import { isSupabaseConfigured } from '../lib/supabaseAuth'
import type { VerificationLevel } from '../lib/types'

function Toggle({ on, onChange, label, detail }: { on: boolean; onChange: (v: boolean) => void; label: string; detail: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-ink-700/70 px-4 py-3 last:border-0">
      <div className="min-w-0">
        <div className="text-[15.5px] text-paper-100">{label}</div>
        <p className="mt-0.5 max-w-[58ch] text-[13.5px] leading-relaxed text-paper-500">{detail}</p>
      </div>
      <button
        role="switch"
        aria-checked={on}
        onClick={() => onChange(!on)}
        className={`relative mt-0.5 h-[18px] w-[32px] shrink-0 rounded-full border transition-colors ${
          on ? 'border-accent-500 bg-accent-900' : 'border-ink-500 bg-ink-800'
        }`}
      >
        <span
          className={`absolute top-[2px] h-[12px] w-[12px] rounded-full transition-all ${
            on ? 'left-[16px] bg-accent-400' : 'left-[2px] bg-paper-400'
          }`}
        />
      </button>
    </div>
  )
}

export function SettingsPage() {
  const [level, setLevel] = useState<VerificationLevel>('strict')
  const [strictLeakage, setStrictLeakage] = useState(true)
  const [quarantine, setQuarantine] = useState(true)
  const [stream, setStream] = useState(true)
  const [notifyFail, setNotifyFail] = useState(true)
  const [notifyVerify, setNotifyVerify] = useState(false)

  return (
    <div className="flex h-full min-w-0 flex-col">
      <PageHeader
        title="Settings"
        subtitle="Workspace defaults applied to new experiments. Existing runs keep the settings they executed under."
      />
      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <section className="overflow-hidden rounded-md border border-ink-600 bg-ink-900">
            <SectionTitle>Defaults for new experiments</SectionTitle>
            <div className="px-4 py-3.5">
              <div className="label-xs mb-2">Verification level</div>
              <div className="flex overflow-hidden rounded-sm border border-ink-600">
                {(['fast', 'standard', 'strict'] as VerificationLevel[]).map((l) => (
                  <button
                    key={l}
                    onClick={() => setLevel(l)}
                    className={`flex-1 border-r border-ink-600 px-3 py-1.5 text-[14px] transition last:border-r-0 ${
                      level === l
                        ? 'bg-accent-900/70 text-accent-300'
                        : 'bg-ink-850 text-paper-400 hover:bg-ink-800 hover:text-paper-200'
                    }`}
                  >
                    {l}
                  </button>
                ))}
              </div>
              <p className="mt-2 text-[13.5px] leading-relaxed text-paper-500">
                Strict runs independent recompute of every claim plus a clean-container replay of the frozen pipeline.
              </p>

              <div className="mt-4 grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1.5">
                  <span className="label-xs">Default metric</span>
                  <select
                    defaultValue="recall"
                    className="h-[30px] rounded-sm border border-ink-600 bg-ink-850 px-2 text-[15px] text-paper-100 outline-none focus:border-accent-500"
                  >
                    {['recall', 'precision', 'roc_auc', 'f1', 'mae', 'log_loss'].map((m) => (
                      <option key={m}>{m}</option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="label-xs">Compute budget</span>
                  <select
                    defaultValue="12 fit-min"
                    className="h-[30px] rounded-sm border border-ink-600 bg-ink-850 px-2 text-[15px] text-paper-100 outline-none focus:border-accent-500"
                  >
                    {['5 fit-min', '12 fit-min', '20 fit-min', '45 fit-min', '90 fit-min'].map((b) => (
                      <option key={b}>{b}</option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          </section>

          <section className="overflow-hidden rounded-md border border-ink-600 bg-ink-900">
            <SectionTitle>Verification policy</SectionTitle>
            <Toggle
              on={strictLeakage}
              onChange={setStrictLeakage}
              label="Block on leakage detection"
              detail="Fail the run immediately if any probe finds a post-outcome feature in the schema."
            />
            <Toggle
              on={quarantine}
              onChange={setQuarantine}
              label="Quarantine conflicting claims"
              detail="Claims where independent recompute disagrees are removed from the final report instead of being shown with a warning."
            />
            <Toggle
              on={stream}
              onChange={setStream}
              label="Stream agent decisions live"
              detail="Push DECISION and METRIC events to the workspace runtime stream while the run is executing."
            />
          </section>

          <section className="overflow-hidden rounded-md border border-ink-600 bg-ink-900">
            <SectionTitle>Notifications</SectionTitle>
            <Toggle
              on={notifyFail}
              onChange={setNotifyFail}
              label="Run failures"
              detail="Notify when a stage exhausts retries or the budget is exceeded."
            />
            <Toggle
              on={notifyVerify}
              onChange={setNotifyVerify}
              label="Verification complete"
              detail="Notify when the verifier finishes recompute and signs the evidence bundle."
            />
          </section>

          <section className="overflow-hidden rounded-md border border-ink-600 bg-ink-900">
            <SectionTitle>API access</SectionTitle>
            <div className="px-4 py-3.5">
              <div className="label-xs mb-1.5">Auth mode</div>
              <div className="flex items-center gap-2">
                <code className="mono min-w-0 flex-1 truncate rounded-sm border border-ink-700 bg-ink-850 px-2 py-1.5 text-[13.5px] text-paper-300">
                  {isDevTokenAllowed()
                    ? 'Bearer JWT · POST /auth/dev-token (local dev)'
                    : isSupabaseConfigured()
                      ? 'Bearer JWT · Supabase Auth'
                      : 'Bearer JWT · Supabase / Better Auth'}
                </code>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-[13.5px] text-paper-500">
                {isDevTokenAllowed() ? (
                  <Badge tone="verify">dev token mint</Badge>
                ) : (
                  <Badge tone="verify">production auth</Badge>
                )}
                <Badge tone="dim">Authorization header</Badge>
              </div>
              <p className="mt-3 text-[13.5px] leading-relaxed text-paper-500">
                {isDevTokenAllowed() ? (
                  <>
                    Local dev: the UI obtains a backend JWT via{' '}
                    <span className="mono text-paper-300">/api/v1/auth/dev-token</span> and sends it as a
                    Bearer token. The production backend disables that endpoint — there the token comes
                    from Supabase Auth / Better Auth instead.
                  </>
                ) : (
                  <>
                    The UI sends a Supabase Auth / Better Auth JWT as a Bearer token, verified by the
                    backend against <span className="mono text-paper-300">GET /api/v1/auth/me</span>. The
                    dev-token minter is disabled in production. Separate workspace API keys are not
                    implemented in this backend.
                  </>
                )}
              </p>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
