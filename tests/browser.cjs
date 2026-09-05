// Runs only against tests.browser_server (an in-memory device). Never a physical phone.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

async function main() {
  const python = process.env.GEOPORT_TEST_PYTHON || path.resolve(
    process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
  const server = spawn(python, ['-m', 'tests.browser_server'], {
    stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true,
  });
  let logs = '';
  server?.stdout.on('data', (data) => { logs += data; });
  server?.stderr.on('data', (data) => { logs += data; });
  server?.on('error', (error) => { logs += error.message; });
  let browser;
  try {
    let url;
    for (let attempt = 0; attempt < 100; attempt++) {
      url = logs.match(/FAKE_DEVICE_URL=(http:\/\/127\.0\.0\.1:\d+)/)?.[1];
      if (url) break;
      if (server.exitCode !== null) break;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    assert(url, `Test server did not start: ${logs}`);
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    const unexpected = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('request', (request) => {
      if (!request.url().startsWith(url) && !request.url().includes('tile.openstreetmap.org')) {
        unexpected.push(request.url());
      }
    });
    await page.goto(url);
    await page.waitForFunction(() => !document.getElementById('connect').disabled);
    await page.getByRole('button', { name: 'Connect', exact: true }).click();
    await page.waitForFunction(() => document.getElementById('status').textContent === 'Ready');
    await page.getByLabel('Latitude', { exact: true }).fill('37.7749');
    await page.getByLabel('Longitude', { exact: true }).fill('-122.4194');
    await page.getByRole('button', { name: 'Simulate location', exact: true }).click();
    await page.waitForFunction(() => document.getElementById('status').textContent === 'Simulating');
    assert.deepEqual((await (await fetch(`${url}/api/session`)).json()).location, [37.7749, -122.4194]);

    const route = { type: 'FeatureCollection', features: [
      { type: 'Feature', properties: { name: 'Test route' }, geometry: { type: 'LineString',
        coordinates: [[-122.4194, 37.7749], [-122.4144, 37.7799]] } },
    ] };
    await page.locator('#import').setInputFiles({ name: 'route.geojson', mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify(route)) });
    await page.waitForFunction(() => document.getElementById('routes').textContent.includes('Test route'));
    await page.locator('#speed').selectOption('custom');
    await page.locator('#custom-speed').fill('7.25');
    await page.getByRole('button', { name: 'Play route', exact: true }).click();
    await page.waitForFunction(() => document.getElementById('status').textContent === 'Playing route');
    assert.equal((await (await fetch(`${url}/api/session`)).json()).playback.speed_kmh, 7.25);
    await page.waitForFunction(() => document.getElementById('progress').value > 0);
    await page.getByRole('button', { name: 'Pause', exact: true }).click();
    await page.waitForFunction(() => document.getElementById('status').textContent === 'Route paused');
    await page.getByRole('button', { name: 'Resume', exact: true }).click();
    await page.waitForFunction(() => document.getElementById('status').textContent === 'Playing route');
    await page.getByRole('button', { name: 'Restore GPS', exact: true }).click();
    await page.waitForFunction(() => document.getElementById('status').textContent === 'Ready');
    assert.equal((await (await fetch(`${url}/api/session`)).json()).location, null);

    const downloadEvent = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export GeoJSON', exact: true }).click();
    const download = await downloadEvent;
    assert.equal(download.suggestedFilename(), 'geoport.geojson');
    const exported = JSON.parse(fs.readFileSync(await download.path(), 'utf8'));
    assert(exported.features.some((f) => f.geometry.type === 'LineString'));
    assert.equal(unexpected.length, 0, `Unexpected background requests: ${unexpected}`);

    // A failed device operation must be visible and must not claim success.
    await page.route('**/api/location', (route) => route.fulfill({ status: 503,
      contentType: 'application/json', body: JSON.stringify({ error: {
        code: 'device_unavailable', message: 'Test device connection lost. Reconnect.' } }) }));
    await page.getByRole('button', { name: 'Simulate location', exact: true }).click();
    await page.waitForFunction(() => document.getElementById('notice').textContent.includes('Test device connection lost'));
    await page.unroute('**/api/location');
    await page.getByRole('button', { name: 'Disconnect', exact: true }).click();
    await page.waitForFunction(() => document.getElementById('status').textContent === 'Disconnected');
    assert(await page.locator('#simulate').isDisabled());

    fs.mkdirSync('test-results', { recursive: true });
    await page.screenshot({ path: 'test-results/desktop.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: 'test-results/mobile.png', fullPage: true });

    // Losing map JavaScript still leaves the coordinate controls and device API usable.
    const offline = await browser.newPage();
    offline.on('pageerror', (error) => errors.push(error.message));
    await offline.route('**/vendor/leaflet.js', (route) => route.abort());
    await offline.goto(url);
    await offline.waitForFunction(() => !document.getElementById('connect').disabled);
    assert(await offline.locator('#notice').textContent().then((s) => s.includes('Map assets')));
    assert.deepEqual(errors, []);
    console.log('Browser checks passed: connect, atomic update, custom-speed playback, pause/resume, restore, export, HTTP errors, responsive layout, map failure.');
  } finally {
    await browser?.close();
    server?.kill();
  }
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
