export type Tone = 'neutral' | 'accent' | 'verify' | 'warn' | 'conflict' | 'dim'

export function statusTone(status: string): Tone {
  switch (status) {
    case 'VERIFIED':
    case 'COMPLETED':
    case 'completed':
    case 'production':
    case 'champion':
      return 'verify'
    case 'RUNNING':
    case 'QUEUED':
    case 'RETRYING':
    case 'running':
    case 'candidate':
      return 'accent'
    case 'CONFLICTING':
    case 'FAILED':
    case 'failed':
      return 'conflict'
    case 'QUARANTINED':
    case 'CANCELLED':
    case 'archived':
    case 'degraded':
      return 'warn'
    case 'UNVERIFIED':
    case 'CREATED':
    case 'draft':
    case 'paused':
      return 'dim'
    default:
      return 'neutral'
  }
}
