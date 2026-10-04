import { chromium } from 'playwright-core'

const browser = await chromium.launch({
  executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  headless: true,
})
const page = await browser.newPage({ viewport: { width: 1600, height: 950 } })
const reqs = []
page.on('request', (r) => {
  if (r.url().includes('/api/')) reqs.push({ method: r.method(), url: r.url() })
})
page.on('response', async (res) => {
  if (res.url().includes('/api/')) {
    let body = ''
    try { body = (await res.text()).slice(0, 200) } catch {}
    console.log('RES', res.status(), res.url(), body)
  }
})
page.on('requestfailed', (r) => {
  if (r.url().includes('/api/')) console.log('FAIL', r.url(), r.failure()?.errorText)
})
page.on('console', (m) => console.log('CON', m.type(), m.text()))
page.on('pageerror', (e) => console.log('ERR', e.message))

await page.goto('http://127.0.0.1:5173/experiments', { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(8000)
console.log('TEXT', (await page.locator('body').innerText()).slice(0, 800).replace(/\n/g, ' | '))
console.log('REQS', JSON.stringify(reqs, null, 2))
await page.screenshot({ path: 'C:/Users/abhin/AppData/Local/Temp/opencode/e2e/debug-exp.png' })
await browser.close()
