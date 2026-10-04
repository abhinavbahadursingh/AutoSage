import { PageHeader } from '../components/layout/Sidebar'
import { EmptyState } from '../components/ui/Primitives'

export function ModelsPage() {
  return (
    <div className="flex h-full min-w-0 flex-col">
      <PageHeader
        title="Models"
        subtitle="Frozen pipelines produced by verified experiments."
        right={
          <div className="mono hidden text-right text-[13px] leading-relaxed text-paper-500 md:block">
            models API: not available
            <br />
            no GET /models endpoint
          </div>
        }
      />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <EmptyState
          title="Model registry unavailable"
          detail="The backend does not expose a models list endpoint. Model names for individual runs appear on the Experiment workspace from result_summary / config. This page will populate when a models API exists."
        />
      </div>
    </div>
  )
}
