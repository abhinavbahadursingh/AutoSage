import { chromium } from 'playwright-core'

const browser = await chromium.launch({
  executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  headless: true,
})
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 })
page.on('pageerror', (e) => console.log('PAGE ERROR:', e.message))
await page.goto('http://localhost:5199/brag.html', { waitUntil: 'load' })
await page.waitForFunction(() => typeof window.__frame === 'function')
await page.evaluate(async () => {
  await document.fonts.ready
})
for (const t of [12.5, 13.7, 14.0, 14.3]) {
  await page.evaluate((tt) => window.__frame(tt), t)
  const info = await page.evaluate(() => {
    const band = document.querySelector('.brag-band')
    return {
      band: band ? band.textContent : null,
      bandOpacity: band ? getComputedStyle(band).opacity : null,
      h1: document.querySelector('h1')?.textContent ?? null,
      aside: Boolean(document.querySelector('aside')),
    }
  })
  console.log(t, JSON.stringify(info))
}
await browser.close()
