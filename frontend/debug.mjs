import { chromium } from 'playwright-core'

const browser = await chromium.launch({
  executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  headless: true,
})
const page = await browser.newPage({ viewport: { width: 1600, height: 950 } })
await page.goto('http://localhost:5183/', { waitUntil: 'networkidle' })
await page.getByRole('button', { name: /re-run/i }).click()
await page.waitForTimeout(6400)
const header = await page.locator('section').first().innerText()
const nodes = await page.locator('section').first().locator('button[title]').evaluateAll((els) =>
  els.map((e) => ({
    title: e.getAttribute('title'),
    cls: e.querySelector('span')?.className ?? '',
    text: e.innerText.replace(/\n/g, ' | '),
  })),
)
console.log('HEADER:\n', header)
console.log('NODES:', JSON.stringify(nodes, null, 2))
await browser.close()
