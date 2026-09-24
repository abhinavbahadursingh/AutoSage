export function fmtInt(n: number): string {
  return n.toLocaleString('en-US')
}

export function fmtPct(n: number, digits = 1): string {
  return `${(n * 100).toFixed(digits)}%`
}

export function fmtMs(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  const m = Math.floor(ms / 60_000)
  const s = Math.round((ms % 60_000) / 1000)
  return `${m}m ${s.toString().padStart(2, '0')}s`
}

export function nowStamp(): string {
  const d = new Date()
  const p = (n: number, l = 2) => n.toString().padStart(l, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}.${p(d.getMilliseconds(), 3)}`
}

export function shortHash(len = 8): string {
  const hex = '0123456789abcdef'
  let out = ''
  for (let i = 0; i < len; i++) out += hex[Math.floor(Math.random() * 16)]
  return out
}
