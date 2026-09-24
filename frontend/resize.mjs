import { readFileSync, writeFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

function walk(dir, out = []) {
  for (const f of readdirSync(dir)) {
    const p = join(dir, f)
    if (statSync(p).isDirectory()) walk(p, out)
    else if (/\.(tsx|ts|css)$/.test(f)) out.push(p)
  }
  return out
}

function mapSize(n) {
  if (n >= 40) return Math.round(n * 1.16)
  const v = n * 1.15 + 1
  return Math.round(v * 2) / 2
}

let changed = 0
for (const file of walk('src')) {
  const src = readFileSync(file, 'utf8')
  const next = src.replace(/text-\[([\d.]+)px\]/g, (m, d) => {
    const n = parseFloat(d)
    const mapped = mapSize(n)
    if (mapped !== n) changed++
    return `text-[${mapped}px]`
  })
  if (next !== src) writeFileSync(file, next)
}
console.log('sizes updated:', changed)
