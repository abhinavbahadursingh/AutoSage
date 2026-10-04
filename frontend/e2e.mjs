import { chromium } from 'playwright-core'
import { mkdirSync } from 'node:fs'

const OUT = 'C:/Users/abhin/AppData/Local/Temp/opencode/e2e'
mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch({
  executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  headless: true,
})
const page = await browser.newPage({ viewport: { width: 1600, height: 950 } })
const errors = []
const apiCalls = []
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(m.text())
})
page.on('pageerror', (e) => errors.push('PAGE: ' + e.message))
page.on('response', async (res) => {
  const url = res.url()
  if (url.includes('/api/')) {
    apiCalls.push({ status: res.status(), url: url.replace('http://127.0.0.1:5173', '') })
  }
})

const shot = async (name) => {
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: false })
  console.log('shot', name)
}

try {
  await page.goto('http://127.0.0.1:5173/', { waitUntil: 'domcontentloaded', timeout: 20000 })
  await page.waitForTimeout(2500)
  await shot('01-home')
  const homeText = await page.locator('body').innerText()
  console.log('HOME_HAS_AUTOSAGE', homeText.includes('AutoSage'))

  await page.goto('http://127.0.0.1:5173/experiments', { waitUntil: 'domcontentloaded', timeout: 20000 })
  await page.waitForTimeout(2500)
  await shot('02-experiments')
  const expText = await page.locator('body').innerText()
  console.log('EXPERIMENTS_SNIPPET', expText.slice(0, 500).replace(/\n/g, ' | '))

  await page.goto('http://127.0.0.1:5173/workspace', { waitUntil: 'domcontentloaded', timeout: 20000 })
  await page.waitForTimeout(2000)
  await shot('03-workspace')
  const wsText = await page.locator('body').innerText()
  console.log('WORKSPACE_SNIPPET', wsText.slice(0, 600).replace(/\n/g, ' | '))

  // Open first experiment if list is on experiments page
  await page.goto('http://127.0.0.1:5173/experiments', { waitUntil: 'domcontentloaded', timeout: 20000 })
  await page.waitForTimeout(2000)
  const rows = page.locator('tbody tr')
  const n = await rows.count()
  console.log('ROW_COUNT', n)
  if (n > 0) {
    await rows.first().click()
    await page.waitForTimeout(1500)
    await shot('04-workspace-from-list')
    const t2 = await page.locator('body').innerText()
    console.log('OPEN_EXP_SNIPPET', t2.slice(0, 500).replace(/\n/g, ' | '))
  }

  await page.goto('http://127.0.0.1:5173/new', { waitUntil: 'domcontentloaded', timeout: 20000 })
  await page.waitForTimeout(1000)
  await shot('05-new')

  await page.goto('http://127.0.0.1:5173/evidence', { waitUntil: 'domcontentloaded', timeout: 20000 })
  await page.waitForTimeout(1500)
  await shot('06-evidence')

  await page.goto('http://127.0.0.1:5173/memory', { waitUntil: 'domcontentloaded', timeout: 20000 })
  await page.waitForTimeout(1500)
  await shot('07-memory')

  await page.goto('http://127.0.0.1:5173/datasets', { waitUntil: 'domcontentloaded', timeout: 20000 })
  await page.waitForTimeout(1500)
  await shot('08-datasets')

  await page.goto('http://127.0.0.1:5173/models', { waitUntil: 'domcontentloaded', timeout: 20000 })
  await page.waitForTimeout(1000)
  await shot('09-models')

  // Create + run via UI
  await page.goto('http://127.0.0.1:5173/new', { waitUntil: 'domcontentloaded', timeout: 20000 })
  await page.waitForTimeout(800)
  const runBtn = page.getByRole('button', { name: /Run Experiment/i })
  if (await runBtn.count()) {
    await runBtn.click()
    await page.waitForTimeout(8000)
    await shot('10-after-create')
    const after = await page.locator('body').innerText()
    console.log('AFTER_CREATE', after.slice(0, 700).replace(/\n/g, ' | '))
  }

  console.log('API_CALLS', JSON.stringify(apiCalls, null, 2))
  console.log('CONSOLE_ERRORS', JSON.stringify(errors, null, 2))
} catch (e) {
  console.error('E2E_FAIL', e.message)
  await shot('error')
}

await browser.close()
