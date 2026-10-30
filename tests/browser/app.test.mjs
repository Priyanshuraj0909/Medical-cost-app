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
  await page.locator('#submit').click();
  await page.locator('#result').waitFor({ state: 'visible' });
}

test('real predictions, explanations, comparison, export and stale-result handling', async () => {
  const { page, errors } = await pageFor();
  try {
    await estimate(page);
    assert.equal(await page.locator('#warnings').isVisible(), false);
    assert.match(await page.locator('#dataset-note').innerText(), /Currency and total versus out-of-pocket cost definition are not documented/);
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
    assert.ok(summary.comparison);
    assert.equal('profile' in summary, false);
    await page.locator('#clear-baseline').click();
    assert.equal(await page.locator('#comparison').isVisible(), false);
    await page.locator('[name="daily_steps"]').fill('20000');
    await estimate(page);
    assert.equal(await page.locator('#warnings').isVisible(), true);
    assert.match(await page.locator('#warning-list').innerText(), /Daily steps is outside/);
    await page.locator('[name="daily_steps"]').fill('7000');
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
