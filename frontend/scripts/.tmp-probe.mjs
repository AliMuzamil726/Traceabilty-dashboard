import { chromium } from 'playwright';

const BASE = 'http://localhost:5173';
const browser = await chromium.launch({
  executablePath: `${process.env.LOCALAPPDATA}\\ms-playwright\\chromium-1247\\chrome-win64\\chrome.exe`,
});
const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, permissions: ['geolocation'], geolocation: { latitude: 30.1575, longitude: 71.5249 } });
page.on('console', (m) => console.log('[console]', m.type(), m.text()));
page.on('pageerror', (e) => console.log('[pageerror]', e.message));

await page.goto(`${BASE}/login`);
await page.getByRole('radio', { name: 'Admin' }).check();
await page.locator('input[type="password"]').fill('12345678');
await page.getByRole('button', { name: 'Sign in' }).click();
await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 20000 });

await page.goto(`${BASE}/register/farmers/985000a7-e759-4c0c-b5ff-9095bee4154a/fields/new`);
await page.getByRole('button', { name: 'Show the corners of 1001-01' }).waitFor({ timeout: 20000 });
await page.waitForTimeout(800);

await page.getByRole('button', { name: 'Show the corners of 1001-01' }).click();
const dialog = page.getByRole('dialog');
await dialog.waitFor();
console.log('dialog title:', await dialog.getByRole('heading').first().textContent());
await page.screenshot({ path: 'scripts/.tmp-drawer-1.png' });

const before = await dialog.boundingBox();
console.log('dialog box before scroll:', before);
await page.mouse.move(900, 500);
await page.mouse.wheel(0, 300);
await page.waitForTimeout(600);
console.log('dialog count after wheel:', await page.getByRole('dialog').count());
const stillVisible = await dialog.isVisible().catch(() => false);
console.log('dialog visible after scroll:', stillVisible);
if (stillVisible) console.log('dialog box after scroll:', await dialog.boundingBox());
await page.screenshot({ path: 'scripts/.tmp-drawer-2.png' });

// Also try scrolling the window directly.
await page.evaluate(() => window.scrollBy(0, 400));
await page.waitForTimeout(400);
console.log('dialog visible after window scroll:', await page.getByRole('dialog').isVisible().catch(() => false));
await page.screenshot({ path: 'scripts/.tmp-drawer-3.png' });

await browser.close();
