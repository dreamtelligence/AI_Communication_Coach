import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const { chromium, webkit } = require('playwright')
const fixture = await readFile(new URL('./fixtures/daily-call.mjs', import.meta.url), 'utf8')

for (const engine of ['chromium', 'webkit']) {
  const browser = await ({ chromium, webkit }[engine]).launch({
    headless: true,
    ...(engine === 'chromium' && process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}),
  })
  try {
    for (const mode of ['finish', 'disconnect', 'analysis-error', 'late-status', 'auto-finish']) {
      const page = await browser.newPage({ viewport: { width: 393, height: 852 } })
      page.setDefaultTimeout(10_000)
      const errors = []
      let analyses = 0
      let finish
      let delayedStatus
      let statusStarted
      const pending = new Promise(resolve => { finish = resolve })
      const statusPending = new Promise(resolve => { statusStarted = resolve })
      page.on('pageerror', error => errors.push(error.message))
      await page.route('**/api/scenarios', route => route.fulfill({ json: { scenarios: [{
        id: 'salary', title: 'Gehaltsverhandlung', category: 'Beruf', icon: 'dollar', description: 'Übungsgespräch',
        avatar_role: 'Führungskraft', user_goal: 'Gehalt verhandeln',
        practice_sides: [{ id: 'employee', label: 'Mitarbeiter/in', user_role: 'Mitarbeiter/in', avatar_role: 'Führungskraft', user_goal: 'Gehalt verhandeln' }],
      }] } }))
      await page.route('**/api/session/status', route => route.fulfill({ json: { configured: true } }))
      await page.route(/(?:@daily-co_daily-js|daily-iframe-esm|daily-esm)[^/]*\.js/, route => route.fulfill({ contentType: 'text/javascript', body: fixture }))
      await page.route('**/api/session/create', route => route.fulfill({ json: {
        conversation_id: 'cfixture1234', session_token: 'fixture-token', embed_url: 'https://tavus.daily.co/fixture',
      } }))
      await page.route('**/api/session/cfixture1234/**', route => {
        if (mode === 'late-status' && route.request().url().endsWith('/status')) {
          delayedStatus = route
          statusStarted()
          return
        }
        return route.fulfill({ json: { status: mode === 'auto-finish' ? 'ended' : 'active' } })
      })
      await page.route('**/api/session/analyze', async route => {
        analyses++
        await pending
        await route.fulfill(mode === 'analysis-error'
          ? { status: 502, json: { error: 'Analyse-Dienst vorübergehend nicht erreichbar.' } }
          : { json: { summary: 'Der Bericht wurde vollständig erstellt.' } })
      })
      try {
        await page.goto(process.env.CHECK_URL || 'http://127.0.0.1:3295/')
        await page.getByRole('button', { name: 'Gespräch starten', exact: true }).click()
        await page.getByRole('button', { name: 'Mikrofon ausschalten', exact: true }).waitFor()
        if (mode === 'late-status') await statusPending
        if (mode !== 'disconnect') {
          if (mode !== 'auto-finish') await page.getByRole('button', { name: 'Beenden und auswerten', exact: true }).click()
          await page.getByText('Gespräch wird ausgewertet …', { exact: true }).waitFor()
        }
        if (delayedStatus) {
          await delayedStatus.fulfill({ json: { status: 'ended' } })
          await page.waitForTimeout(100)
        }
        await page.evaluate(() => window.__videoFixture.disconnect())
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)))
        if (mode === 'disconnect') {
          await page.getByRole('heading', { name: 'Videoverbindung nicht verfügbar' }).waitFor()
          assert.equal(analyses, 0, 'A real disconnect must not trigger paid analysis')
        } else {
          assert.equal(await page.getByRole('heading', { name: 'Videoverbindung nicht verfügbar' }).isVisible(), false,
            'The expected video shutdown must not replace the pending report with a connection error')
          assert.equal(await page.locator('.video-call').count(), 0, 'Analysis must release the live media component')
          assert.equal(analyses, 1)
          finish()
          await page.getByRole('heading', { name: 'Deine Auswertung' }).waitFor()
          await page.getByText(mode === 'analysis-error'
            ? 'Analyse-Dienst vorübergehend nicht erreichbar.'
            : 'Der Bericht wurde vollständig erstellt.', { exact: true }).waitFor()
        }
        assert.deepEqual(errors, [])
        console.log(`${engine}: ${mode} passed`)
      } finally {
        finish()
        await page.close()
      }
    }
  } finally { await browser.close() }
}
