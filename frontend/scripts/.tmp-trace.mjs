import { chromium } from 'playwright';

const BASE = 'http://localhost:5173';
const browser = await chromium.launch({
  executablePath: `${process.env.LOCALAPPDATA}\\ms-playwright\\chromium-1247\\chrome-win32\\chrome.exe`,
}).catch(() =>
  chromium.launch({
    executablePath: `${process.env.LOCALAPPDATA}\\ms-playwright\\chromium-1247\\chrome-win64\\chrome.exe`,
  }),
);
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));

await page.goto(`${BASE}/login`);
await page.getByRole('radio', { name: 'Admin' }).check();
await page.locator('input[type="password"]').fill('12345678');
await page.getByRole('button', { name: 'Sign in' }).click();
await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 20000 });

await page.goto(`${BASE}/qr?crop=cotton&lot=MUX-G1-H01&trace=MUX-G1-H01`);
await page.getByText('Verification').waitFor({ timeout: 20000 });
const checks = await page.locator('section,div').filter({ hasText: /closed after processing/ }).first().textContent().catch(() => 'none');
console.log('verification mentions:', (await page.getByText(/closed after processing/).count()), checks?.slice(0, 120));
await page.getByText('Verification').scrollIntoViewIfNeeded();
await page.screenshot({ path: 'scripts/.tmp-trace.png' });

await browser.close();
