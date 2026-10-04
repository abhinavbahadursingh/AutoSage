import type { Experiment, ExperimentResult } from '../lib/types'
import { shortHash } from '../lib/format'

function slug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
    .slice(0, 30)
}

const baseResult: ExperimentResult = {
  bestPipeline: '',
  reproducibility: [
    { label: 'Experiment ID', value: '' },
    { label: 'Dataset hash', value: '' },
    { label: 'Artifact digest', value: '' },
    { label: 'Replay command', value: '' },
  ],
  pipelineSteps: [
    { op: 'load', detail: '' },
    { op: 'profile', detail: '' },
    { op: 'preprocess', detail: '' },
    { op: 'select', detail: '' },
    { op: 'train', detail: '' },
    { op: 'evaluate', detail: '' },
    { op: 'verify', detail: '' },
    { op: 'freeze', detail: '' },
  ],
}

export function resultFor(exp: Experiment): ExperimentResult {
  const pipeline = `autosage_${slug(exp.name) || 'run'}_v1`
  return {
    ...baseResult,
    bestPipeline: pipeline,
    reproducibility: baseResult.reproducibility.map((r) => {
      if (r.label === 'Experiment ID') return { ...r, value: exp.id }
      if (r.label === 'Dataset hash') return { ...r, value: `sha256:${shortHash(4)}…${shortHash(4)}` }
      if (r.label === 'Artifact digest') return { ...r, value: `sha256:${shortHash(4)}…${shortHash(4)}` }
      if (r.label === 'Replay command') return { ...r, value: `autosage replay ${exp.id}` }
      return r
    }),
    pipelineSteps: baseResult.pipelineSteps.map((s) =>
      s.op === 'load' ? { ...s, detail: `${exp.dataset} · verified provenance` } : s,
    ),
  }
}
