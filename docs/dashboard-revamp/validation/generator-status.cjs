// Browser reads only; fixtures stay local and no workload actions are clicked.
const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const url = process.env.DASHBOARD_URL || 'http://127.0.0.1:18765';
assert.ok(['http://127.0.0.1:18765', 'https://mlops.titipin.me'].includes(url));
const live = url.startsWith('https:');
const output = process.env.QA_OUTPUT || '/tmp/generator-status-qa';
const checks = [], errors = [], writes = [];
const check = (ok, label) => { assert.ok(ok, label); checks.push(label); };
async function settle(page) {
  await page.getByRole('heading', { name: 'Workload Injector', exact: true }).waitFor();
  await page.waitForFunction(() => document.querySelector('[data-testid="stApp"]')?.getAttribute('data-test-script-state') === 'notRunning');
  await page.waitForFunction(() => ![...document.querySelectorAll('[data-stale="true"]')].some(e => e.getBoundingClientRect().width));
}
async function refresh(page) {
  if (!await page.getByRole('button', { name: 'Refresh now', exact: true }).isVisible()) await page.getByTestId('stExpandSidebarButton').click();
  await page.getByRole('button', { name: 'Refresh now', exact: true }).click();
  await page.waitForTimeout(450); await settle(page);
}
async function fixture(page, state) {
  assert.equal(live, false);
  await fetch(`http://127.0.0.1:18766/__state?value=generator_${state}`);
  await refresh(page);
}
(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: '/home/oktaavsm/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome' });
  const page = await browser.newPage({ viewport: { width: 1448, height: 1100 } });
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => { if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(r.method())) writes.push(r.url()); });
  await page.goto(url);
  await page.getByTestId('stSidebar').getByText('Workload Injector', { exact: true }).click();
  await settle(page);
  await page.getByText('Auto-refresh', { exact: true }).click(); await settle(page);
  const summary = page.getByRole('region', { name: 'Generator status summary', exact: true });
  for (const theme of ['dark', 'light']) {
    await page.setViewportSize({ width: 1448, height: 1100 });
    await page.getByRole('button', { name: 'Main menu', exact: true }).click();
    await page.getByTestId('stMainMenuItem-theme-' + (theme === 'dark' ? 'Dark' : 'Light')).click();
    await page.keyboard.press('Escape'); await refresh(page);
    await page.waitForFunction(expected => getComputedStyle(document.documentElement).getPropertyValue('--bg').trim() === expected, theme === 'dark' ? '#101418' : '#F4F6F9');
    for (const width of [1448, 1024, 768, 390, 320]) {
      await page.setViewportSize({ width, height: width < 500 ? 1500 : 1100 });
      await page.waitForTimeout(250);
      check(await summary.locator('.generator-card').count() === 5, `${theme} ${width}: profile, connection and three independent metric cards`);
      const geometry = await summary.evaluate(el => [...el.querySelectorAll('.generator-card, .generator-request')].map(e => {
        const r = e.getBoundingClientRect(); return { left: r.left, right: r.right, clipped: e.scrollWidth > e.clientWidth + 1 };
      }));
      check(geometry.every(r => r.left >= -1 && r.right <= width + 1 && !r.clipped), `${theme} ${width}: summary cards contained without clipping`);
      check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${theme} ${width}: no horizontal page overflow`);
      check(await summary.locator('h3').evaluate(el => parseFloat(getComputedStyle(el).fontSize)) >= 25, `${theme} ${width}: profile name at least 25px`);
      const positions = await summary.locator('.generator-top .generator-card').evaluateAll(es => es.map(e => e.getBoundingClientRect().top));
      check(width >= 1120 ? Math.abs(positions[0] - positions[1]) < 2 : positions[1] > positions[0], `${theme} ${width}: deliberate desktop/mobile reflow`);
      if ([1448, 390].includes(width)) {
        await page.getByTestId('stMain').evaluate(el => { el.scrollTop = 0; });
        await page.screenshot({ path: `${output}/${live ? 'live' : 'qa'}-${theme}-${width}.png` });
      }
    }
    await page.setViewportSize({ width: 390, height: 1500 });
    await page.evaluate(() => { document.documentElement.style.fontSize = '32px'; });
    check(await summary.evaluate(el => [...el.querySelectorAll('.generator-card, .generator-request')].every(e => e.scrollWidth <= e.clientWidth + 1)), `${theme}: 200% text without summary clipping`);
    await page.evaluate(() => { document.documentElement.style.fontSize = ''; });
  }
  await page.setViewportSize({ width: 1448, height: 1100 });
  if (!live) {
    for (const [state, label] of Object.entries({ STEADY_NORMAL: 'Steady normal', BURST_BUSY: 'Rush hour', FLASH_ANOMALY: 'Flash sale', COOLING_DOWN: 'Cooling down', IDLE_SILENT: 'Quiet night', DRIFT_ANOMALY: 'Drift anomaly' })) {
      await fixture(page, state);
      check(await summary.locator('h3').innerText() === label, `${state}: human-readable observed profile`);
    }
    await fixture(page, 'pending');
    check(await summary.locator('h3').innerText() === 'Steady normal', 'Pending request never replaces observed profile');
    check((await summary.locator('.generator-request').innerText()).includes('Requested profile: Rush hour'), 'Pending request is separately named');
    await page.screenshot({ path: `${output}/qa-pending.png` });
    await fixture(page, 'offline');
    check((await summary.innerText()).includes('Last reported profile') && (await summary.innerText()).includes('Heartbeat stale'), 'Offline profile clearly last-known');
    check(await page.getByRole('button', { name: 'Request rush hour', exact: true }).isDisabled(), 'Offline write controls disabled');
    await page.screenshot({ path: `${output}/qa-offline.png` });
    for (const state of ['empty', 'error']) {
      await fixture(page, state);
      check((await summary.innerText()).includes('No profile reported') && !(await summary.innerText()).includes('0 VUs'), `${state}: missing values do not become zero`);
    }
    await fixture(page, 'zero');
    check((await summary.innerText()).includes('0 VUs') && (await summary.innerText()).includes('00:00'), 'Observed zero values stay zero');
    await fixture(page, 'STEADY_NORMAL');
  }
  if (!await page.getByRole('button', { name: 'Refresh now', exact: true }).isVisible()) await page.getByTestId('stExpandSidebarButton').click();
  await page.getByRole('button', { name: 'Refresh now', exact: true }).focus();
  await page.keyboard.press('Tab'); await page.keyboard.press('Shift+Tab');
  check(await page.getByRole('button', { name: 'Refresh now', exact: true }).evaluate(el => el.matches(':focus-visible')), 'Keyboard refresh has visible focus');
  await page.keyboard.press('Enter'); await page.waitForTimeout(500); await settle(page);
  check(await page.getByTestId('stException').count() === 0, 'No Streamlit exception');
  check(writes.length === 0, 'Browsing status never sends browser write requests');
  check(errors.length === 0, 'No browser JavaScript errors');
  fs.writeFileSync(`${output}/${live ? 'live' : 'qa'}.json`, JSON.stringify({ verified_at: new Date().toISOString(), source: live ? 'Public production reads; no operational actions' : 'Local synthetic fixtures only', count: checks.length, checks, errors }, null, 2));
  console.log(`PASS ${checks.length} generator status checks`);
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
