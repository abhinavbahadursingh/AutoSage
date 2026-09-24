import { chromium } from 'playwright-core'
import { mkdirSync } from 'node:fs'

const OUT = 'C:/Users/abhin/AppData/Local/Temp/opencode/shots3'
mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch({
  executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  headless: true,
})
const page = await browser.newPage({ viewport: { width: 1600, height: 950 } })
page.on('console', (m) => {
  if (m.type() === 'error') console.log('CONSOLE ERROR:', m.text())
})
page.on('pageerror', (e) => console.log('PAGE ERROR:', e.message))

const shot = async (name) => {
  await page.screenshot({ path: `${OUT}/${name}.png` })
  console.log('shot', name)
}

await page.goto('http://localhost:5183/', { waitUntil: 'networkidle' })
await page.waitForTimeout(1400)
await shot('home-hero')
await page.evaluate(() => document.querySelector('.overflow-y-auto')?.scrollTo(0, 1050))
await page.waitForTimeout(500)
await shot('home-what')
await page.evaluate(() => document.querySelector('.overflow-y-auto')?.scrollTo(0, 2200))
await page.waitForTimeout(500)
await shot('home-how')
await page.evaluate(() => document.querySelector('.overflow-y-auto')?.scrollTo(0, 3600))
await page.waitForTimeout(500)
await shot('home-start')

await page.goto('http://localhost:5183/workspace', { waitUntil: 'networkidle' })
await page.waitForTimeout(900)
await shot('workspace')

await page.locator('button[title*="Evaluate"]').click()
await page.waitForTimeout(500)
await shot('drawer')
await page.getByRole('button', { name: 'Analysis' }).click()
await page.waitForTimeout(500)
await shot('drawer-analysis')
await page.keyboard.press('Escape')

await page.getByRole('button', { name: /re-run/i }).click()
await page.waitForTimeout(7000)
const timelineText = await page.locator('section').first().innerText()
console.log('TIMELINE:', timelineText.replace(/\n/g, ' | '))
await shot('running')

for (const [path, name] of [
  ['/evidence', 'evidence'],
  ['/memory', 'memory'],
  ['/experiments', 'experiments'],
]) {
  await page.goto('http://localhost:5183' + path, { waitUntil: 'networkidle' })
  await page.waitForTimeout(700)
  await shot(name)
}

await browser.close()
