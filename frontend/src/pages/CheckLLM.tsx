import { useCallback, useEffect, useState } from 'react'
import { PageHeader } from '../components/layout/Sidebar'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/Primitives'
import { api, ApiError, type LlmCheckResult, type LlmStatus } from '../lib/api'
import { useStore } from '../store/context'

const PRESET_MODELS = [
  'groq/openai/gpt-oss-20b',
  'groq/openai/gpt-oss-120b',
  'groq/qwen/qwen3.8-27b',
  'groq/allam-2-7b',
  'groq/llama-3.1-8b-instant',
  'openrouter/meta-llama/llama-3.3-70b-instruct',
]

export function CheckLLMPage() {
  const { toast } = useStore()
  const [status, setStatus] = useState<LlmStatus | null>(null)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [model, setModel] = useState('')
  const [checking, setChecking] = useState(false)
  const [checkResult, setCheckResult] = useState<LlmCheckResult | null>(null)
  const [checkError, setCheckError] = useState<string | null>(null)
  const [selecting, setSelecting] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const s = await api.llmStatus()
      setStatus(s)
      setStatusError(null)
      setModel((m) => m || s.default_model || s.fast_model)
    } catch (err) {
      setStatusError(err instanceof ApiError ? err.message : 'Failed to load LLM status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const runCheck = async () => {
    const target = model.trim()
    if (!target) return
    setChecking(true)
    setCheckError(null)
    try {
      const res = await api.llmCheck(target)
      setCheckResult(res)
      toast({
        title: res.ok ? 'Model responding' : 'Model check failed',
        detail: res.ok
          ? `${res.provider ?? '—'} · ${res.latency_ms ?? '?'} ms`
          : (res.error ?? 'probe failed').slice(0, 120),
        tone: res.ok ? 'success' : 'error',
      })
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Check request failed'
      setCheckError(msg)
      setCheckResult(null)
      toast({ title: 'Check failed', detail: msg, tone: 'error' })
    } finally {
      setChecking(false)
    }
  }

  const useModel = async () => {
    const target = model.trim()
    if (!target) return
    setSelecting(true)
    try {
      const s = await api.llmSelect(target)
      setStatus(s)
      toast({ title: 'Model selected', detail: `${target} will be used for further processing. Restart the worker to apply it to running workers.`, tone: 'success' })
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Select request failed'
      toast({ title: 'Could not set model', detail: msg, tone: 'error' })
    } finally {
      setSelecting(false)
    }
  }

  return (
    <div className="flex h-full min-w-0 flex-col">
      <PageHeader
        title="CheckLLM"
        subtitle="Probe whether your configured LLM responds, then set it as the model used for further processing."
        right={
          <button
            onClick={() => void refresh()}
            className="flex h-[28px] items-center rounded-sm border border-ink-600 bg-ink-850 px-2.5 text-[14px] text-paper-200 transition hover:bg-ink-800"
          >
            Refresh
          </button>
        }
      />
      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        <div className="grid max-w-[1100px] gap-4 lg:grid-cols-2">
          <section className="overflow-hidden rounded-md border border-ink-600 bg-ink-900">
            <div className="flex items-center justify-between border-b border-ink-600 px-4 py-2.5">
              <h3 className="label-xs text-paper-300">Current configuration</h3>
              <span className="mono text-[12.5px] text-paper-500">GET /llm/status</span>
            </div>
            {loading ? (
              <EmptyState title="Loading…" />
            ) : statusError ? (
              <EmptyState title="Could not load LLM status" detail={statusError} />
            ) : !status ? (
              <EmptyState title="No status" />
            ) : (
              <div className="p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={status.default_model ? 'verify' : 'dim'}>
                    {status.default_model ? 'override active' : 'tier defaults'}
                  </Badge>
                  {status.providers.map((p) => (
                    <Badge key={p} tone="accent">{p}</Badge>
                  ))}
                </div>
                <dl className="mt-3 flex flex-col gap-1.5">
                  <Row k="default model" v={status.default_model || '— (tier defaults)'} />
                  <Row k="fast model" v={status.fast_model} />
                  <Row k="reasoning model" v={status.reasoning_model} />
                  <Row k="fallback order" v={status.fallback_order.join(' → ')} />
                </dl>
              </div>
            )}
          </section>

          <section className="overflow-hidden rounded-md border border-ink-600 bg-ink-900">
            <div className="flex items-center justify-between border-b border-ink-600 px-4 py-2.5">
              <h3 className="label-xs text-paper-300">Probe a model</h3>
              <span className="mono text-[12.5px] text-paper-500">POST /llm/check</span>
            </div>
            <div className="p-4">
              <label className="label-xs mb-1.5 block text-paper-400">Model id (provider/model)</label>
              <input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                list="preset-models"
                placeholder="groq/openai/gpt-oss-20b"
                className="mono w-full rounded-sm border border-ink-600 bg-ink-850 px-2.5 py-2 text-[14px] text-paper-100 outline-none focus:border-accent-500"
              />
              <datalist id="preset-models">
                {PRESET_MODELS.map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  onClick={() => void runCheck()}
                  disabled={checking || !model.trim()}
                  className="flex h-[30px] items-center rounded-sm border border-accent-500 bg-accent-500 px-3 text-[14px] font-medium text-ink-950 transition hover:bg-accent-400 disabled:cursor-not-allowed disabled:border-ink-600 disabled:bg-ink-750 disabled:text-paper-500"
                >
                  {checking ? 'Checking…' : 'Check model'}
                </button>
                <button
                  onClick={() => void useModel()}
                  disabled={selecting || !model.trim()}
                  className="flex h-[30px] items-center rounded-sm border border-ink-600 bg-ink-850 px-3 text-[14px] text-paper-100 transition hover:bg-ink-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {selecting ? 'Setting…' : 'Use this model'}
                </button>
              </div>

              {checkError && (
                <p className="mt-3 text-[13.5px] text-[var(--as-error)]">{checkError}</p>
              )}
              {checkResult && (
                <div className="mt-4 rounded-sm border border-ink-700 bg-ink-850/70 px-3 py-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={checkResult.ok ? 'verify' : 'conflict'}>
                      {checkResult.ok ? 'responding' : 'not responding'}
                    </Badge>
                    {checkResult.provider && (
                      <span className="mono text-[12.5px] text-paper-400">provider {checkResult.provider}</span>
                    )}
                    {checkResult.latency_ms != null && (
                      <span className="mono text-[12.5px] text-paper-400">{checkResult.latency_ms} ms</span>
                    )}
                  </div>
                  <p className="mono mt-1.5 break-all text-[12.5px] text-paper-500">{checkResult.model}</p>
                  {checkResult.sample && (
                    <p className="mt-1 text-[13.5px] text-paper-300">sample: “{checkResult.sample}”</p>
                  )}
                  {checkResult.error && (
                    <p className="mt-1.5 break-all text-[13px] leading-relaxed text-[var(--as-error)]">{checkResult.error}</p>
                  )}
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-ink-700/70 pb-1 last:border-0">
      <span className="text-[13px] text-paper-500">{k}</span>
      <span className="mono min-w-0 truncate text-right text-[13.5px] text-paper-100">{v}</span>
    </div>
  )
}
