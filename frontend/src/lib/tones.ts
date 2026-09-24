import type { VerificationStatus } from './types'

export type Tone = 'neutral' | 'accent' | 'verify' | 'warn' | 'conflict' | 'dim'

export function statusTone(status: VerificationStatus | string): Tone {
  switch (status) {
    case 'VERIFIED':
    case 'completed':
    case 'production':
    case 'champion':
      return 'verify'
    case 'running':
    case 'candidate':
      return 'accent'
    case 'CONFLICTING':
    case 'failed':
      return 'conflict'
    case 'QUARANTINED':
    case 'archived':
    case 'degraded':
      return 'warn'
    case 'UNVERIFIED':
    case 'draft':
    case 'paused':
      return 'dim'
    default:
      return 'neutral'
  }
}
