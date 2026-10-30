import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { spawn } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';

let server;
let browser;
let base;
let output = '';
before(async () => {
  server = spawn(process.env.PYTHON_BIN || 'python', ['-m', 'uvicorn', 'app:app', '--host', '127.0.0.1', '--port', '0'], { stdio: ['ignore', 'pipe', 'pipe'] });
  const append = chunk => { output += chunk; };
  server.stdout.on('data', append); server.stderr.on('data', append);
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    const match = output.match(/http:\/\/127\.0\.0\.1:(\d+)/);
    if (match) { base = match[0]; break; }
    if (server.exitCode !== null) throw new Error(`Preview failed: ${output}`);
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.ok(base, `Preview did not start: ${output}`);
  browser = await chromium.launch({
    ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
    headless: true,
  });
});
after(async () => { await browser?.close(); server?.kill('SIGTERM'); });

async function pageFor(viewport = { width: 1280, height: 900 }) {
  const context = await browser.newContext({ viewport, reducedMotion: 'reduce' });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.goto(base);
  return { page, errors };
}
async function estimate(page) {
  for (let attempt = 0; attempt < 3 && await page.locator('#next').isVisible(); attempt++) await page.locator('#next').click();
  assert.equal(await page.locator('#submit').isVisible(), true, await page.locator('#error').textContent());
  await page.locator('#submit').click();
  await page.locator('#result').waitFor({ state: 'visible' });
}

test('real predictions, explanations, comparison, export and stale-result handling', async () => {
  const { page, errors } = await pageFor();
  try {
    await estimate(page);
    assert.equal(await page.locator('#warnings').isVisible(), false);
    assert.match(await page.locator('#dataset-note').innerText(), /Original currency and total versus out-of-pocket cost definition are not documented/);
    assert.equal(await page.locator('#amount').innerText(), '₹1,094.90');
    assert.match(await page.locator('#monthly').innerText(), /^₹/);
    await page.locator('#model-details summary').click();
    assert.match(await page.locator('#dataset-details').innerText(), /original dataset source is not recorded/);
    await page.locator('#model-details summary').click();
    if (process.env.DESKTOP_SCREENSHOT_PATH) await page.screenshot({ path: process.env.DESKTOP_SCREENSHOT_PATH, fullPage: true });
    assert.equal(await page.locator('#factors li').count(), 5);
    assert.match(await page.locator('#uncertainty').innerText(), /unavailable/);
    await page.locator('#pin').click();
    await page.locator('[name="hospital_admissions"]').fill('2');
    assert.equal(await page.locator('#result').isVisible(), false);
    await estimate(page);
    assert.equal(await page.locator('#comparison').isVisible(), true);
    assert.match(await page.locator('#changed-fields').innerText(), /Hospital admissions: 0 → 2/);
    const downloadPromise = page.waitForEvent('download');
    await page.locator('#download').click();
    const download = await downloadPromise;
    const summary = JSON.parse(await readFile(await download.path(), 'utf8'));
    assert.ok(summary.estimate.explanation);
    assert.equal(summary.display_currency.currency, 'INR');
    assert.equal(summary.display_currency.conversion_applied, false);
    assert.ok(summary.comparison);
    assert.equal('profile' in summary, false);
    await page.locator('#clear-baseline').click();
    assert.equal(await page.locator('#comparison').isVisible(), false);
    await page.locator('[data-step="1"]').click();
    await page.locator('[name="daily_steps"]').fill('20000');
    await estimate(page);
    assert.equal(await page.locator('#warnings').isVisible(), true);
    assert.match(await page.locator('#warning-list').innerText(), /Daily steps is outside/);
    await page.locator('[data-step="1"]').click();
    await page.locator('[name="daily_steps"]').fill('7000');
    await page.locator('[data-step="2"]').click();
    await page.locator('#insurance-type').selectOption('no_insurance');
    assert.equal(await page.locator('#coverage-percent').inputValue(), '0');
    assert.equal(await page.locator('#coverage-percent').isDisabled(), true);
    await estimate(page);
    assert.deepEqual(errors, []);
    const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    assert.deepEqual(accessibility.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.map(n => n.target) })), []);
  } finally { await page.context().close(); }
});

test('mobile layout, keyboard entry, and accessibility', async () => {
  const { page, errors } = await pageFor({ width: 390, height: 844 });
  try {
    await page.keyboard.press('Tab');
    assert.equal(await page.locator('.skip-link').evaluate(el => el === document.activeElement), true);
    await page.keyboard.press('Enter');
    await estimate(page);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    assert.deepEqual(accessibility.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })), []);
    assert.deepEqual(errors, []);
    if (process.env.SCREENSHOT_PATH) await page.screenshot({ path: process.env.SCREENSHOT_PATH, fullPage: true });
  } finally { await page.context().close(); }
});

test('failed prediction hides old results and lets the user retry', async () => {
  const { page } = await pageFor();
  try {
    await estimate(page);
    await page.route('**/predict', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Estimate temporarily unavailable' }) }));
    await page.locator('#submit').click();
    await page.locator('#error').waitFor({ state: 'visible' });
    assert.match(await page.locator('#error').innerText(), /temporarily unavailable/);
    assert.equal(await page.locator('#result').isVisible(), false);
    assert.equal(await page.locator('#submit').isDisabled(), false);
    await page.unroute('**/predict');
    await estimate(page);
  } finally { await page.context().close(); }
});

test('guided form validates fields and preserves their values across steps', async () => {
  const { page } = await pageFor();
  try {
    assert.equal(await page.locator('[data-form-step="0"]').isVisible(), true);
    assert.equal(await page.locator('[data-form-step="1"]').isVisible(), false);
    await page.locator('[name="age"]').fill('17');
    await page.locator('#next').click();
    assert.equal(await page.locator('[data-form-step="0"]').isVisible(), true);
    assert.match(await page.locator('#error-age').innerText(), /at least 18/);
    await page.locator('[name="age"]').fill('42');
    await page.locator('#next').click();
    assert.equal(await page.locator('[data-form-step="1"]').isVisible(), true);
    await page.locator('#previous').click();
    assert.equal(await page.locator('[name="age"]').inputValue(), '42');
    await page.locator('#view-all').click();
    assert.equal(await page.locator('[data-form-step]:visible').count(), 3);
    await estimate(page);
    assert.ok(await page.locator('#amount').innerText());
  } finally { await page.context().close(); }
});

test('scenario explores a separate profile and a printable PDF omits form inputs', async () => {
  const { page, errors } = await pageFor();
  try {
    await estimate(page);
    const amount = await page.locator('#amount').innerText();
    const admissions = await page.locator('[name="hospital_admissions"]').inputValue();
    await page.locator('#scenario-value').fill('3');
    await page.locator('#scenario-calculate').click();
    await page.locator('#scenario-result').waitFor({ state: 'visible' });
    assert.notEqual(await page.locator('#scenario-amount').innerText(), amount);
    assert.equal(await page.locator('#amount').innerText(), amount);
    assert.equal(await page.locator('[name="hospital_admissions"]').inputValue(), admissions);
    assert.equal(await page.locator('#scenario-chart').evaluate(canvas => Boolean(window.Chart.getChart(canvas))), true);
    await page.evaluate(() => { window.print = () => { window.printCalled = true; }; });
    await page.locator('#print').click();
    assert.equal(await page.evaluate(() => window.printCalled), true);
    assert.match(await page.locator('#print-report').textContent(), /Scenario comparison/);
    assert.match(await page.locator('#print-report').textContent(), /INR|Indian rupees/);
    assert.equal(await page.locator('#print-report input').count(), 0);
    await page.emulateMedia({ media: 'print' });
    assert.equal(await page.locator('#main').isVisible(), false);
    assert.equal(await page.locator('#print-report').isVisible(), true);
    const pdf = await page.pdf({ format: 'A4' });
    assert.equal(pdf.subarray(0, 4).toString(), '%PDF');
    assert.ok(pdf.length > 5000);
    await page.emulateMedia({ media: 'screen' });
    const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    assert.deepEqual(accessibility.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })), []);
    await page.locator('#scenario-value').fill('2');
    assert.equal(await page.locator('#scenario-result').isVisible(), false);
    assert.deepEqual(errors, []);
  } finally { await page.context().close(); }
});

test('Hindi, dark theme and reports work without storing health profiles', async () => {
  const { page, errors } = await pageFor({ width: 390, height: 844 });
  try {
    await page.locator('#language').selectOption('hi');
    assert.equal(await page.locator('html').getAttribute('lang'), 'hi-IN');
    assert.match(await page.locator('h1').innerText(), /चिकित्सा/);
    await estimate(page);
    assert.equal(await page.locator('#result-heading').innerText(), 'आपका सालाना खर्च अनुमान');
    assert.match(await page.locator('#factors').innerText(), /कम|अधिक/);
    await page.locator('#theme').click();
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    assert.deepEqual(accessibility.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })), []);
    await page.evaluate(() => { window.print = () => {}; });
    await page.locator('#print').click();
    assert.match(await page.locator('#print-report').textContent(), /अनुमान रिपोर्ट/);
    await page.emulateMedia({ media: 'print' });
    const pdf = await page.pdf({ format: 'A4' });
    assert.equal(pdf.subarray(0, 4).toString(), '%PDF');
    await page.emulateMedia({ media: 'screen' });
    assert.deepEqual(await page.evaluate(() => Object.keys(localStorage).sort()), ['careestimate-language', 'careestimate-theme']);
    if (process.env.HINDI_SCREENSHOT_PATH) await page.screenshot({ path: process.env.HINDI_SCREENSHOT_PATH, fullPage: true });
    await page.reload();
    assert.equal(await page.locator('html').getAttribute('lang'), 'hi-IN');
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
    assert.equal(await page.locator('#result').isVisible(), false);
    assert.deepEqual(errors, []);
  } finally { await page.context().close(); }
});

test('installed app shell works offline and never caches predictions or profiles', async () => {
  const { page } = await pageFor();
  const context = page.context();
  try {
    await page.evaluate(async () => { await navigator.serviceWorker.ready; });
    await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller));
    await estimate(page);
    const paths = await page.evaluate(async () => {
      const values = [];
      for (const key of await caches.keys()) for (const request of await (await caches.open(key)).keys()) values.push(new URL(request.url).pathname);
      return values;
    });
    assert.ok(paths.includes('/static/app.js'));
    assert.ok(paths.every(path => path === '/' || path.startsWith('/static/')));
    assert.equal(paths.includes('/predict'), false);
    assert.equal(paths.includes('/model-info'), false);
    await context.setOffline(true);
    await page.reload();
    await page.locator('#connection-note').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#result').isVisible(), false);
    assert.match(await page.locator('#connection-note').innerText(), /predictions need an internet/);
    assert.equal(await page.evaluate(() => window.CareCharts !== undefined && window.Chart !== undefined), true);
    await context.setOffline(false);
    await estimate(page);
  } finally { await context.setOffline(false); await context.close(); }
});

test('waterfall reconciles and workspace saves, renames, exports and clears scenarios', async () => {
  const { page, errors } = await pageFor();
  try {
    await estimate(page);
    assert.equal(await page.locator('#waterfall-table tbody tr').count(), 22);
    const values = await page.locator('#contribution-chart').evaluate(canvas => window.Chart.getChart(canvas).data.datasets[0].data);
    assert.equal(values.length, 22);
    assert.ok(Math.abs(values.at(-2)[1] - values.at(-1)[1]) < 0.005);
    for (let value = 1; value <= 6; value++) {
      await page.locator('#scenario-value').fill(String(value));
      await page.locator('#scenario-calculate').click();
      await page.locator('#scenario-result').waitFor({ state: 'visible' });
      await page.locator('#scenario-save').click();
    }
    assert.equal(await page.locator('#workspace-table tbody tr').count(), 6);
    await page.locator('#scenario-save').click();
    assert.match(await page.locator('#workspace-message').innerText(), /six scenarios/);
    await page.locator('#workspace-table input').first().fill('My scenario');
    await page.locator('#workspace-heading').click();
    const pending = page.waitForEvent('download'); await page.locator('#download').click();
    const summary = JSON.parse(await readFile(await (await pending).path(), 'utf8'));
    assert.equal(summary.saved_scenarios.length, 6);
    assert.equal(summary.saved_scenarios[0].name, 'My scenario');
    assert.equal('profile' in summary.saved_scenarios[0], false);
    await page.locator('#workspace-table button').first().click();
    assert.equal(await page.locator('#workspace-table tbody tr').count(), 5);
    await page.locator('#workspace-clear').click();
    assert.equal(await page.locator('#workspace-results').isVisible(), false);
    assert.deepEqual(errors, []);
  } finally { await page.context().close(); }
});

test('mobile CSV preview, partial prediction, download and clearing', async () => {
  const { page, errors } = await pageFor({ width: 390, height: 844 });
  try {
    const template = await readFile('static/batch-template.csv', 'utf8');
    const text = template.trimEnd() + '\n' + template.split('\n')[1].replace('35,female', '17,female') + '\n';
    await page.locator('#batch-file').setInputFiles({ name: 'profiles.csv', mimeType: 'text/csv', buffer: Buffer.from(text) });
    await page.waitForFunction(() => !document.querySelector('#batch-validate').disabled);
    await page.locator('#batch-validate').click();
    await page.waitForFunction(() => !document.querySelector('#batch-predict').disabled);
    assert.equal(await page.locator('#batch-rows tr').count(), 2);
    assert.match(await page.locator('#batch-status').innerText(), /1 valid, 1 invalid, 0 predicted/);
    await page.locator('#batch-predict').click();
    await page.waitForFunction(() => !document.querySelector('#batch-download').disabled);
    assert.match(await page.locator('#batch-status').innerText(), /1 predicted/);
    assert.match(await page.locator('#batch-rows').innerText(), /₹1,094.90/);
    const pending = page.waitForEvent('download'); await page.locator('#batch-download').click();
    const csv = await readFile(await (await pending).path(), 'utf8');
    assert.match(csv, /1094.9/); assert.match(csv, /invalid/); assert.match(csv, /currency unspecified/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    assert.deepEqual(accessibility.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })), []);
    await page.locator('#batch-clear').click();
    assert.equal(await page.locator('#batch-results').isVisible(), false);
    assert.equal(await page.locator('#batch-download').isDisabled(), true);
    assert.deepEqual(errors, []);
  } finally { await page.context().close(); }
});
