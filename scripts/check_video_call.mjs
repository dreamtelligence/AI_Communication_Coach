import assert from 'node:assert/strict'
import { readFile, mkdir } from 'node:fs/promises'
import { createRequire } from 'node:module'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const { chromium, webkit, devices } = require('playwright')
const fixture = await readFile(new URL('./fixtures/daily-call.mjs', import.meta.url), 'utf8')
const output = process.env.CHECK_OUTPUT || '/tmp/coach-video-check'
await mkdir(output, { recursive: true })
for (const engine of ['chromium', 'webkit']) {
  const browser = await ({ chromium, webkit }[engine]).launch({
    headless: true,
    ...(engine === 'chromium' && process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}),
  })
  try {
    for (const width of [320, 393, 768, 1440]) {
      const page = await browser.newPage({
        ...(engine === 'webkit' && width === 393 ? devices['iPhone 13'] : {}),
        viewport: { width, height: 852 },
      })
      const errors = []
      const calls = []
      let expired = false
      let analyses = 0
      if (engine === 'chromium' && width === 393) await page.clock.install()
      page.on('pageerror', e => errors.push(e.message))
      await page.route(/(?:@daily-co_daily-js|daily-iframe-esm|daily-esm)[^/]*\.js/, r => r.fulfill({ contentType: 'text/javascript', body: fixture }))
      await page.route('**/api/session/create', r => r.fulfill({ json: {
        conversation_id: 'cfixture1234', session_token: 'fixture-token', embed_url: 'https://tavus.daily.co/fixture',
      } }))
      await page.route('**/api/session/cfixture1234/**', r => {
        calls.push(new URL(r.request().url()).pathname)
        return r.fulfill({ json: { status: expired ? 'ended' : 'active', connection_expired: expired } })
      })
      await page.route('**/api/session/analyze', r => {
        analyses++
        return r.fulfill({ json: {} })
      })
      await page.goto(process.env.CHECK_URL || 'http://127.0.0.1:3291/')
      await page.getByRole('button', { name: 'Gespräch starten', exact: true }).click()
      await page.getByRole('button', { name: 'Mikrofon ausschalten', exact: true }).waitFor()
      await page.waitForFunction(() => document.querySelector('.avatar-video')?.readyState >= 2)
      const boxes = await page.locator('.stage--call').evaluate(el => {
        const stage = el.getBoundingClientRect()
        const video = el.querySelector('.avatar-video').getBoundingClientRect()
        const self = el.querySelector('.self-preview').getBoundingClientRect()
        const controls = el.querySelector('.video-controls').getBoundingClientRect()
        return { stage: stage.toJSON(), video: video.toJSON(), self: self.toJSON(), controls: controls.toJSON(), overflow: document.documentElement.scrollWidth > innerWidth }
      })
      assert.ok(boxes.stage.width > 240 && boxes.stage.height > 240, 'Call stage must not collapse')
      assert.equal(boxes.video.height, boxes.stage.height)
      assert.ok(boxes.self.width >= 84 && boxes.self.width < boxes.stage.width / 3)
      assert.ok(boxes.self.right <= boxes.stage.right && boxes.self.top >= boxes.stage.top)
      if (width < 760) {
        assert.ok(Math.abs(boxes.self.height / boxes.self.width - 1.5) < 0.02, 'Mobile preview must retain width and double its original height')
        assert.ok(Math.abs(boxes.stage.bottom - boxes.self.bottom - 16) < 1, 'Mobile preview needs a bottom inset')
        assert.ok(Math.abs(boxes.stage.right - boxes.self.right - 16) < 1, 'Mobile preview needs a right inset')
        assert.ok(boxes.controls.right + 8 < boxes.self.left, 'Media buttons must not overlap the mobile preview')
      } else {
        assert.ok(Math.abs(boxes.self.height / boxes.self.width - 0.75) < 0.02, 'Desktop preview keeps its landscape ratio')
        assert.ok(Math.abs(boxes.self.top - boxes.stage.top - 64) < 1, 'Desktop preview keeps its upper corner')
      }
      assert.equal(boxes.overflow, false)
      assert.equal(calls.filter(p => p.endsWith('/end')).length, 0, 'StrictMode must not end a new call')
      await page.getByRole('button', { name: 'Mikrofon ausschalten', exact: true }).click()
      await page.getByRole('button', { name: 'Mikrofon einschalten', exact: true }).waitFor()
      await page.getByRole('button', { name: 'Kamera ausschalten', exact: true }).click()
      await page.getByRole('button', { name: 'Kamera einschalten', exact: true }).waitFor()
      await page.getByRole('button', { name: 'Kamera einschalten', exact: true }).click()
      await page.screenshot({ path: `${output}/${engine}-${width}.png`, fullPage: true })
      if (engine === 'chromium' && width === 393) {
        await page.waitForRequest(r => r.url().endsWith('/heartbeat'), { timeout: 20_000 })
        await page.evaluate(() => window.__videoFixture.freeze())
        const count = calls.filter(p => p.endsWith('/heartbeat')).length
        await page.clock.fastForward(60_000)
        await page.waitForTimeout(100)
        assert.equal(calls.filter(p => p.endsWith('/heartbeat')).length, count, 'A frozen video must stop renewing the lease')
        await page.clock.resume()
      }
      const released = page.waitForResponse(r => r.url().endsWith('/end'), { timeout: 3_000 })
      await page.getByRole('button', { name: 'Audio-Analyse', exact: true }).click()
      if (engine === 'chromium' && width === 393) await page.clock.runFor(100)
      await released
      assert.ok(calls.some(p => p.endsWith('/end')), 'Unmount must release the provider session')
      if (engine === 'chromium' && width === 393) {
        await page.getByRole('button', { name: 'Live-Training', exact: true }).click()
        await page.getByRole('button', { name: 'Gespräch starten', exact: true }).click()
        await page.getByRole('button', { name: 'Mikrofon ausschalten', exact: true }).waitFor()
        expired = true
        await page.clock.runFor(5500)
        await page.getByRole('button', { name: 'Zurück zur Auswahl', exact: true }).waitFor()
        assert.equal(analyses, 0, 'An abandoned call must not trigger paid analysis')
      }
      assert.deepEqual(errors, [])
      console.log(`${engine} ${width}px: ${boxes.stage.width} × ${boxes.stage.height}, PiP/controls/release passed`)
      await page.close()
    }
  } finally { await browser.close() }
}
