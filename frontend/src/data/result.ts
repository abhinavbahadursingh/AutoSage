import type { Experiment, ExperimentResult } from '../lib/types'
import { shortHash } from '../lib/format'
import { CHURN_RESULT as base } from './experiments'

function slug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
    .slice(0, 30)
}

export function resultFor(exp: Experiment): ExperimentResult {
  const pipeline = `autosage_${slug(exp.name) || 'run'}_v1`
  return {
    ...base,
    bestPipeline: pipeline,
    reproducibility: base.reproducibility.map((r) => {
      if (r.label === 'Experiment ID') return { ...r, value: exp.id }
      if (r.label === 'Dataset hash') return { ...r, value: `sha256:${shortHash(4)}…${shortHash(4)}` }
      if (r.label === 'Artifact digest') return { ...r, value: `sha256:${shortHash(4)}…${shortHash(4)}` }
      if (r.label === 'Replay command') return { ...r, value: `autosage replay ${exp.id}` }
      return r
    }),
    pipelineSteps: base.pipelineSteps.map((s) =>
      s.op === 'load' ? { ...s, detail: `${exp.dataset} · verified provenance` } : s,
    ),
  }
}
