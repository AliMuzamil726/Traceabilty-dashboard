import { chromium } from 'playwright';

const BASE = 'http://localhost:5173';
const browser = await chromium.launch({
  executablePath: `${process.env.LOCALAPPDATA}\\ms-playwright\\chromium-1247\\chrome-win64\\chrome.exe`,
});
const page = await browser.newPage({
  viewport: { width: 1024, height: 700 },
  permissions: ['geolocation'],
  geolocation: { latitude: 30.1575, longitude: 71.5249 },
});
page.on('pageerror', (e) => console.log('[pageerror]', e.message));

await page.goto(`${BASE}/login`);
await page.getByRole('radio', { name: 'Admin' }).check();
await page.locator('input[type="password"]').fill('12345678');
await page.getByRole('button', { name: 'Sign in' }).click();
await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 20000 });

await page.goto(`${BASE}/register/farmers/985000a7-e759-4c0c-b5ff-9095bee4154a/fields/new`);
const trigger = page.getByRole('button', { name: 'Show the corners of 1001-03' });
await trigger.waitFor({ timeout: 20000 });

// Scroll the page down so the field table sits in view, like a user looking at the rows.
await trigger.scrollIntoViewIfNeeded();
await page.waitForTimeout(500);
console.log('scrollTop before open:', await page.evaluate(() => document.documentElement.scrollTop));
await trigger.click();
const dialog = page.getByRole('dialog');
await dialog.waitFor();
await page.waitForTimeout(500);
console.log('box open:', await dialog.boundingBox());
await page.screenshot({ path: 'scripts/.tmp-d2-open.png' });

// Wheel over the page area to the left of the drawer, then over the drawer itself.
await page.mouse.move(300, 400);
await page.mouse.wheel(0, 240);
await page.waitForTimeout(400);
console.log(
  'after wheel left: dialogs=',
  await page.getByRole('dialog').count(),
  'pageScrollTop=',
  await page.evaluate(() => document.documentElement.scrollTop),
  'bodyOverflow=',
  await page.evaluate(() => getComputedStyle(document.body).overflowY),
);
await page.screenshot({ path: 'scripts/.tmp-d2-left.png' });

const box = await dialog.boundingBox();
await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
await page.mouse.wheel(0, 240);
await page.waitForTimeout(400);
console.log('after wheel inside:', await page.getByRole('dialog').count(), await dialog.boundingBox().catch(() => null));
await page.screenshot({ path: 'scripts/.tmp-d2-inside.png' });

// Drag the scrollbar-ish: press PageDown
await page.keyboard.press('PageDown');
await page.waitForTimeout(400);
console.log('after PageDown:', await page.getByRole('dialog').count());
await page.screenshot({ path: 'scripts/.tmp-d2-pagedown.png' });

await browser.close();
