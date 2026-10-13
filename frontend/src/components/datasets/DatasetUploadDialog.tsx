/**
 * DatasetUploadDialog — the "dataset not found" prompt.
 *
 * Two triggers converge here: a pre-run upload that did not land, and a run
 * that the discovery agent parked mid-pipeline because the dataset search
 * agent could not resolve the dataset (under maintenance, or never uploaded).
 *
 * In both cases the user picks a file and the run continues — in the parked
 * case the caller restarts the experiment, so the pipeline resumes from the
 * top now that the file exists.
 *
 * Overlay structure mirrors `AgentDrawer`: a `z-40` backdrop that closes on
 * click plus a `z-50` panel, Escape to dismiss.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Database, FileUp, Loader2, Upload, X } from 'lucide-react'
import { api, ApiError } from '../../lib/api'

/** Extensions the backend accepts (mirrors settings.ALLOWED_UPLOAD_TYPES). */
const ACCEPT = '.csv,text/csv,application/csv,text/plain'

function fmtBytes(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

export function DatasetUploadDialog({
  datasetName,
  onClose,
  onUploaded,
}: {
  /** The dataset discovery asked for. Empty/"no dataset selected" when the run named none. */
  datasetName: string
  /** Abandon the run without starting it. */
  onClose: () => void
  /** Called with the stored filename so the caller can resume the run. */
  onUploaded: (name: string) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  // The backend sends this sentinel when the run named no dataset at all —
  // it is a prompt for the user, not a filename, so it must not be rendered
  // as "the file we are looking for".
  const unnamed = !datasetName || /no dataset selected/i.test(datasetName)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  // Move focus into the dialog so Escape/Tab behave and screen readers
  // announce it as soon as it opens.
  useEffect(() => {
    panelRef.current?.focus()
  }, [])

  const pick = useCallback((next: File | null) => {
    setError(null)
    setFile(next)
  }, [])

  const upload = useCallback(async () => {
    if (!file || uploading) return
    setUploading(true)
    setError(null)
    try {
      const res = await api.uploadDataset(file)
      // The backend sanitizes the filename; use what it actually stored so
      // the resumed run asks for a name that really exists.
      onUploaded(res.name || file.name)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed. Try again.')
      setUploading(false)
    }
  }, [file, onUploaded, uploading])

  const nameMismatch = !unnamed && file != null && file.name !== datasetName

  return (
    <>
      <div className="anim-fade-in fixed inset-0 z-40 bg-ink-950/45" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dataset-upload-title"
        tabIndex={-1}
        className="anim-fade-in fixed left-1/2 top-1/2 z-50 w-[min(520px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-md border border-ink-600 bg-ink-900 shadow-[0_24px_64px_-24px_rgba(0,0,0,0.9)] outline-none"
      >
        <header className="flex items-start justify-between gap-3 border-b border-ink-600 px-5 py-4">
          <div className="flex min-w-0 items-start gap-3">
            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-sm border border-accent-500/40 bg-accent-500/10">
              <Database size={14} className="text-accent-400" />
            </span>
            <div className="min-w-0">
              <h2 id="dataset-upload-title" className="text-[17px] font-semibold text-paper-50">
                {unnamed ? 'The discovery agent needs a dataset' : 'Dataset not found'}
              </h2>
              <p className="mt-1 text-[14px] leading-relaxed text-paper-400">
                {unnamed
                  ? 'Your run started without a dataset. The pipeline is paused at the discovery stage — attach a file to continue.'
                  : `The dataset search agent could not find ${datasetName}. The pipeline is paused at the discovery stage.`}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            disabled={uploading}
            className="shrink-0 text-paper-500 transition hover:text-paper-100 disabled:opacity-40"
          >
            <X size={15} />
          </button>
        </header>

        <div className="flex flex-col gap-4 px-5 py-4">
          {!unnamed && (
            <div className="flex items-center gap-2 rounded-sm border border-ink-600 bg-ink-850 px-3 py-2.5">
              <Database size={13} className="shrink-0 text-paper-500" />
              <span className="label-xs shrink-0">Looking for</span>
              <span className="mono min-w-0 flex-1 truncate text-[14px] text-accent-300" title={datasetName}>
                {datasetName}
              </span>
            </div>
          )}

          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault()
              if (!uploading) setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              if (uploading) return
              pick(e.dataTransfer.files?.[0] ?? null)
            }}
            disabled={uploading}
            aria-label="Choose the dataset file, or drop it here"
            className={`flex flex-col items-center gap-1.5 rounded-sm border border-dashed px-4 py-7 text-center transition disabled:cursor-not-allowed disabled:opacity-50 ${
              dragging
                ? 'border-accent-500 bg-accent-500/10'
                : 'border-ink-500 bg-ink-850/60 hover:border-accent-500 hover:bg-ink-800'
            }`}
          >
            {file ? (
              <>
                <FileUp size={18} className="text-accent-400" />
                <span className="mono text-[14px] text-paper-100">{file.name}</span>
                <span className="mono text-[12px] text-paper-500">{fmtBytes(file.size)}</span>
              </>
            ) : (
              <>
                <Upload size={18} className={dragging ? 'text-accent-400' : 'text-paper-500'} />
                <span className="text-[14px] text-paper-200">Drop your dataset here</span>
                <span className="mono text-[12px] text-paper-500">
                  or click to browse · CSV · up to 50 MB
                </span>
              </>
            )}
          </button>

          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => pick(e.target.files?.[0] ?? null)}
          />

          {nameMismatch && (
            <p className="text-[13px] leading-relaxed text-warn-500">
              You picked <span className="mono">{file?.name}</span> instead of{' '}
              <span className="mono">{datasetName}</span>. The run will use the file you upload now.
            </p>
          )}

          {error && (
            <p className="rounded-sm border border-conflict-500/40 bg-conflict-500/10 px-3 py-2 text-[13px] text-conflict-400">
              {error}
            </p>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-ink-600 px-5 py-3">
          <button
            onClick={onClose}
            disabled={uploading}
            className="h-[32px] rounded-sm border border-ink-600 px-3 text-[14px] text-paper-300 transition hover:border-ink-500 hover:text-paper-100 disabled:opacity-40"
          >
            Cancel run
          </button>
          <button
            onClick={() => void upload()}
            disabled={!file || uploading}
            className="flex h-[32px] items-center gap-2 rounded-sm border border-accent-500 bg-accent-500 px-3 text-[14px] font-semibold text-ink-950 transition hover:bg-accent-400 disabled:cursor-not-allowed disabled:border-ink-600 disabled:bg-ink-750 disabled:text-paper-500"
          >
            {uploading ? (
              <>
                <Loader2 size={13} className="animate-spin" />
                Uploading…
              </>
            ) : (
              <>
                <FileUp size={13} />
                Upload &amp; resume run
              </>
            )}
          </button>
        </footer>
      </div>
    </>
  )
}