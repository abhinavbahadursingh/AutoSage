/**
 * Layout probe for the Objectives page (repo headless recipe, README
 * "Headless verification recipe"): seed the run pointer, drive the real page
 * with playwright-core, and assert layout invariants.
 *
 *   node layout-check.mjs
 *
 * Invariants asserted:
 *   - main.scrollHeight <= main.clientHeight          (no phantom page scroll)
 *   - gap between the sequence and the Backend Log <= 2px (no dead space)
 *   - the right summary panel is not collapsed (height > 200px)
 *   - the Backend Log reaches the bottom of the body
 *   - the selected objective's details section has the same length as the
 *     Verification Sequence and ends on the same line (after a click)
 */
import { chromium } from 'playwright-core'
import { mkdirSync } from 'node:fs'

const OUT = 'C:/Users/abhin/AppData/Local/Temp/opencode/e2e'
mkdirSync(OUT, { recursive: true })

const RUN_ID = process.env.RUN_ID ?? '6e8e9413-de51-4ad2-b35f-b48b944eaa90'
const BASE = process.env.BASE ?? 'http://127.0.0.1:5173'
const VIEWS = [
  { width: 1920, height: 1080 },
  { width: 1600, height: 950 },
  { width: 1366, height: 768 },
]

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const failures = []

for (const view of VIEWS) {
  const tag = `${view.width}x${view.height}`
  const page = await browser.newPage({ viewport: view })
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text())
  })

  await page.addInitScript((id) => {
    sessionStorage.setItem('as_objective_run', id)
  }, RUN_ID)

  try {
    await page.goto(`${BASE}/objectives`, {
      waitUntil: 'domcontentloaded',
      timeout: 30000,
    })
    await page.waitForSelector('text=Final Verdict', { timeout: 30000 })
    await page.waitForTimeout(1500)
  } catch (e) {
    failures.push(`${tag}: report never rendered (${e.message.split('\n')[0]})`)
    await page.screenshot({ path: `${OUT}/layout-error-${tag}.png` })
    await page.close()
    continue
  }

  await page.screenshot({ path: `${OUT}/layout-${tag}.png` })

  // Select an objective so the details section renders, then measure both.
  try {
    await page.locator('button', { hasText: 'Every decision recorded' }).first().click()
    await page.waitForSelector('h3:has-text("Objective 4")', { timeout: 10000 })
    await page.waitForTimeout(600)
  } catch (e) {
    failures.push(`${tag}: could not select an objective (${e.message.split('\n')[0]})`)
  }

  const data = await page.evaluate(() => {
    const rect = (el) => {
      const r = el.getBoundingClientRect()
      return {
        top: +r.top.toFixed(1),
        bottom: +r.bottom.toFixed(1),
        height: +r.height.toFixed(1),
        width: +r.width.toFixed(1),
      }
    }
    const h3 = (text) =>
      [...document.querySelectorAll('h3')].find((el) => el.textContent?.trim() === text)
    const seqCell = h3('Verification Sequence')?.parentElement?.parentElement ?? null
    const logCell = h3('Backend Log')?.parentElement?.parentElement ?? null
    const detailH3 = [...document.querySelectorAll('h3')].find((el) =>
      el.textContent?.trim().startsWith('Objective '),
    )
    const detailSection = detailH3?.parentElement?.parentElement ?? null
    const grid = seqCell?.parentElement ?? null
    const rightCell = grid?.children[1] ?? null
    const main = document.querySelector('main')
    const header = document.querySelector('header') ?? document.querySelector('h1')
    const seqScroll = seqCell?.children[1] ?? null
    const logConsole = logCell?.children[1] ?? null
    return {
      main: main
        ? { scrollHeight: main.scrollHeight, clientHeight: main.clientHeight, scrollTop: main.scrollTop }
        : null,
      doc: {
        scrollTop: document.documentElement.scrollTop,
        scrollHeight: document.documentElement.scrollHeight,
        clientHeight: document.documentElement.clientHeight,
      },
      header: header ? rect(header) : null,
      h1: (() => {
        const el = document.querySelector('h1')
        if (!el) return null
        const s = getComputedStyle(el)
        return {
          text: el.textContent?.slice(0, 40),
          rect: rect(el),
          color: s.color,
          opacity: s.opacity,
          rects: el.getClientRects().length,
        }
      })(),
      seq: seqCell ? rect(seqCell) : null,
      right: rightCell ? rect(rightCell) : null,
      detail: detailSection ? rect(detailSection) : null,
      log: logCell ? rect(logCell) : null,
      gapAboveLog:
        seqCell && logCell
          ? +(logCell.getBoundingClientRect().top - seqCell.getBoundingClientRect().bottom).toFixed(1)
          : null,
      seqScroll: seqScroll
        ? { scrollHeight: seqScroll.scrollHeight, clientHeight: seqScroll.clientHeight }
        : null,
      logConsole: logConsole ? { clientHeight: logConsole.clientHeight } : null,
      windowH: window.innerHeight,
      bodyH: document.body.clientHeight,
    }
  })

  console.log(tag, JSON.stringify(data, null, 2))

  if (data.main && data.main.scrollHeight > data.main.clientHeight + 1) {
    failures.push(`${tag}: main scrolls (${data.main.scrollHeight} > ${data.main.clientHeight})`)
  }
  if (data.gapAboveLog === null || data.gapAboveLog > 2) {
    failures.push(`${tag}: dead space above the log (${data.gapAboveLog}px)`)
  }
  if (!data.right || data.right.height <= 200) {
    failures.push(`${tag}: right summary panel collapsed (${data.right?.height}px)`)
  }
  if (data.log) {
    const bottomGap = +(data.windowH - data.log.bottom).toFixed(1)
    if (bottomGap > 2) failures.push(`${tag}: log stops ${bottomGap}px above the viewport bottom`)
    if (data.log.height < 188) failures.push(`${tag}: log shorter than its 190px floor (${data.log.height}px)`)
  }
  if (!data.detail) {
    failures.push(`${tag}: selected-objective details section did not render`)
  } else if (data.seq) {
    const lenDiff = +Math.abs(data.detail.height - data.seq.height).toFixed(1)
    const endDiff = +Math.abs(data.detail.bottom - data.seq.bottom).toFixed(1)
    if (lenDiff > 1.5) {
      failures.push(`${tag}: details length ${data.detail.height}px != sequence ${data.seq.height}px`)
    }
    if (endDiff > 1.5) {
      failures.push(`${tag}: details bottom ${data.detail.bottom} != sequence bottom ${data.seq.bottom}`)
    }
  }

  await page.screenshot({ path: `${OUT}/layout-${tag}-selected.png` })
  if (errors.length) console.log(tag, 'PAGE_ERRORS', JSON.stringify(errors))
  await page.close()
}

await browser.close()

if (failures.length) {
  console.log('LAYOUT_FAILURES', JSON.stringify(failures, null, 2))
  process.exitCode = 1
} else {
  console.log('LAYOUT_OK — every invariant held')
}
