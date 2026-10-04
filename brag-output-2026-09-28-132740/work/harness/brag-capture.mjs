import { chromium } from 'playwright-core'
import { mkdirSync } from 'node:fs'

const OUT = process.argv[2]
const MODE = process.argv[3] || 'stills'
const PORT = process.env.PORT || '5199'

mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch({
  executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  headless: true,
  args: ['--force-device-scale-factor=1', '--hide-scrollbars', '--disable-lcd-text'],
})
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 })
page.on('pageerror', (e) => console.log('PAGE ERROR:', e.message))
page.on('console', (m) => {
  if (m.type() === 'error') console.log('CONSOLE ERROR:', m.text())
})

await page.goto(`http://localhost:${PORT}/brag.html`, { waitUntil: 'load' })
await page.waitForFunction(() => typeof (window).__frame === 'function', null, { timeout: 20000 })
await page.evaluate(async () => {
  await document.fonts.load('500 41px "Playfair Display"')
  await document.fonts.load('600 60px "Playfair Display"')
  await document.fonts.load('400 17px "Playfair Display"')
  await document.fonts.load('italic 400 18px "Playfair Display"')
  await document.fonts.load('400 14px "JetBrains Mono"')
  await document.fonts.load('600 13px "JetBrains Mono"')
  await document.fonts.ready
})
console.log('fonts ready')

const frame = async (t) => {
  await page.evaluate((tt) => window.__frame(tt), t)
}

const STILL_TIMES = [
  ['00a-black', 0.02],
  ['00b-typing', 1.35],
  ['00c-preflight', 2.65],
  ['00d-click', 3.0],
  ['01a-scene2-in', 3.55],
  ['01b-running', 5.6],
  ['01c-late-run', 7.4],
  ['01d-transition', 7.76],
  ['02a-zoom', 8.7],
  ['02b-drawer', 11.4],
  ['02c-evidence', 12.5],
  ['03a-scene4', 13.7],
  ['03b-complete', 14.75],
  ['03c-claims', 15.9],
  ['04a-hero', 17.4],
  ['04b-final', 19.8],
]

if (MODE === 'stills') {
  for (const [name, t] of STILL_TIMES) {
    await frame(t)
    await page.screenshot({ path: `${OUT}/${name}.jpg`, type: 'jpeg', quality: 92 })
    console.log('still', name, t)
  }
} else {
  const FPS = 30
  const DURATION = 20
  const N = Math.round(FPS * DURATION)
  const t0 = Date.now()
  for (let i = 0; i < N; i++) {
    const t = i / FPS
    await frame(t)
    await page.screenshot({
      path: `${OUT}/f${String(i).padStart(4, '0')}.jpg`,
      type: 'jpeg',
      quality: 95,
    })
    if (i % 60 === 0) {
      const el = ((Date.now() - t0) / 1000).toFixed(0)
      console.log(`frame ${i}/${N} · ${el}s elapsed`)
    }
  }
  console.log('render done in', ((Date.now() - t0) / 1000).toFixed(1), 's')
}

await browser.close()
