import { chromium } from 'playwright';

const BASE = 'http://localhost:5173';
const browser = await chromium.launch({
  executablePath: `${process.env.LOCALAPPDATA}\\ms-playwright\\chromium-1247\\chrome-win64\\chrome.exe`,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.on('pageerror', (e) => console.log('[pageerror]', e.message));

await page.goto(`${BASE}/login`);
await page.getByRole('radio', { name: 'Admin' }).check();
await page.locator('input[type="password"]').fill('12345678');
await page.getByRole('button', { name: 'Sign in' }).click();
await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 20000 });

// --- sidebar spacing
await page.getByRole('link', { name: 'Home' }).waitFor({ timeout: 20000 });
const gaps = await page.evaluate(() => {
  const navs = [...document.querySelectorAll('nav')].map((n) => n.getAttribute('aria-label'));
  const items = [...document.querySelectorAll('nav[aria-label="Primary"] a, nav[aria-label="Primary"] span[role=link]')];
  const boxes = items.map((i) => i.getBoundingClientRect());
  return { navs, count: items.length, gaps: boxes.slice(1).map((b, i) => Math.round(b.top - boxes[i].bottom)) };
});
console.log('sidebar gaps:', gaps);
await page.screenshot({ path: 'scripts/.tmp-sidebar.png' });

// --- heaps page defaults to all ginners and lists heaps
await page.goto(`${BASE}/heaps`);
await page.waitForTimeout(2500);
const ginnerSelect = page.getByLabel('Ginner');
console.log('heaps ginner select value:', await ginnerSelect.inputValue(), '| text:', await ginnerSelect.locator('option:checked').textContent());
const heapItems = await page.locator('ul[aria-label="Heaps"] li').count();
const heapCards = await page.getByText(/H0\d/).count();
console.log('heap rows:', heapItems, 'heap id mentions:', heapCards);
await page.screenshot({ path: 'scripts/.tmp-heaps.png' });

// --- pick a ginner -> only that ginner's heaps
const options = await ginnerSelect.locator('option').evaluateAll((os) => os.map((o) => ({ v: o.value, t: o.textContent })));
const bwp1 = options.find((o) => o.t.includes('BWP-G1'));
await ginnerSelect.selectOption(bwp1.v);
await page.waitForTimeout(1200);
console.log('BWP-G1 heap rows:', await page.locator('ul[aria-label="Heaps"] li').count());
await page.screenshot({ path: 'scripts/.tmp-heaps-bwp1.png' });

// --- QR page: Find button alignment + farmers section
await page.goto(`${BASE}/qr`);
await page.waitForTimeout(2500);
const input = page.locator('#find-code');
const find = page.getByRole('button', { name: 'Find' });
const [ib, fb] = [await input.boundingBox(), await find.boundingBox()];
console.log('find alignment delta:', Math.round((ib.y + ib.height / 2) - (fb.y + fb.height / 2)));
console.log('qr ginner select text:', await page.getByLabel('Ginner').locator('option:checked').textContent());
const lotSelect = page.getByLabel('Heap', { exact: true });
const lotOptions = await lotSelect.locator('option').evaluateAll((os) => os.map((o) => o.value).filter(Boolean));
console.log('lots available:', lotOptions.length, lotOptions.slice(0, 4));
await lotSelect.selectOption('MUX-G1-H01');
await page.waitForTimeout(2000);
console.log('farmers heading:', await page.getByRole('heading', { name: /^Farmers \(/ }).textContent().catch(() => 'none'));
console.log('farmer chip present:', await page.getByText('Ali Muzamil').count());
await page.screenshot({ path: 'scripts/.tmp-qr.png', fullPage: false });

// --- profile: mobile is required and refuses an empty save
await page.goto(`${BASE}/profile`);
await page.waitForTimeout(1500);
const mobileLabel = page.locator('label', { hasText: 'Mobile' }).first();
console.log('mobile label:', JSON.stringify(await mobileLabel.textContent()));
const mobile = page.getByLabel(/Mobile/, { exact: false });
await mobile.fill('');
await page.getByRole('button', { name: 'Save details' }).click();
await page.waitForTimeout(500);
console.log('mobile error:', await page.getByRole('alert').textContent().catch(() => 'none'));
await mobile.fill('0300-ABC1234');
console.log('mobile after letters typed:', await mobile.inputValue());
await page.screenshot({ path: 'scripts/.tmp-profile.png' });

await browser.close();
