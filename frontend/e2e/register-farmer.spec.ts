import { expect, test, type Page } from '@playwright/test';

/**
 * Each run maps its fields on fresh ground.
 *
 * The map opens at the officer's reported position, and the zero-overlap rule applies
 * across every farmer in the database, so a repeat run that drew on the same spot
 * would legitimately collide with the fields the previous run saved. Moving the
 * officer each run keeps the test independent of what is already stored, which also
 * means it can be run against a shared environment.
 */
const RUN_LOCATION = { latitude: 30.1575, longitude: 71 + Math.random() * 5 };

test.use({ geolocation: RUN_LOCATION });

/**
 * The smoke test for Module 2: register a cotton farmer, draw a field, save it, then
 * add a second field for the same farmer.
 *
 * It exercises the parts no unit test can reach: the CNIC mask feeding the lookup, the
 * SAWIE ID chip, the location cascade against real seeded data, Leaflet and Geoman
 * drawing, the server-side overlap check gating the Save button, and the per-farmer
 * field ID sequence.
 *
 * Map tiles are stubbed, so the test needs no network and does not depend on Esri
 * being reachable.
 */

/** A CNIC that is valid, and different on every run so the test can be repeated. */
function uniqueCnic(): string {
  const seven = String(Date.now()).slice(-7);
  return `35202-${seven}-1`;
}

/** A 1x1 transparent PNG, served in place of every map tile. */
const BLANK_TILE = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  'base64',
);

async function stubTiles(page: Page): Promise<void> {
  await page.route('**/server.arcgisonline.com/**', (route) =>
    route.fulfill({ status: 200, contentType: 'image/png', body: BLANK_TILE }),
  );
}

/**
 * Draw a square field on the map.
 *
 * The points are worked out from the map's own box each time rather than from fixed
 * page coordinates: the page scrolls as banners appear and disappear, and a click at a
 * stale coordinate silently lands somewhere else. `dx` shifts the square sideways so
 * two fields can be drawn without overlapping, which the zero-overlap rule forbids.
 */
async function drawSquare(page: Page, { dx = 0, size = 120 }: { dx?: number; size?: number }) {
  const map = page.locator('.leaflet-container');
  await map.scrollIntoViewIfNeeded();
  await expect(map).toBeVisible();

  // Arm the draw tool unless it is already armed (the toolbar then offers Cancel).
  const draw = page.locator('#main').getByRole('button', { name: 'Draw polygon' });
  if ((await draw.count()) > 0 && (await draw.isEnabled())) await draw.click();

  await page.keyboard.press('Escape'); // dismiss any open field popup
  const box = await map.boundingBox();
  if (!box) throw new Error('The map has no size');

  const cx = box.x + box.width / 2 + dx;
  const cy = box.y + box.height / 2;
  const half = size / 2;
  const corners: Array<[number, number]> = [
    [cx - half, cy - half],
    [cx + half, cy - half],
    [cx + half, cy + half],
    [cx - half, cy + half],
  ];

  for (const [x, y] of corners) {
    await page.mouse.click(x, y);
    await page.waitForTimeout(150);
  }
  // Geoman finishes a polygon when the first vertex is clicked again.
  const [firstX, firstY] = corners[0]!;
  await page.mouse.click(firstX, firstY);
  await page.waitForTimeout(400);
}

test('register a cotton farmer, map a field, then add a second field', async ({ page }) => {
  await stubTiles(page);
  const cnic = uniqueCnic();

  /* ---------------------------------------------------------------- register */

  await page.goto('/register');
  // Scoped to the page body: the sidebar also has a "Register Farmer" link, and
  // Playwright matches accessible names case-insensitively, so an unscoped query
  // would find the navigation item rather than the action.
  const main = page.locator('#main');
  await expect(main.getByRole('heading', { name: 'Register Farmer', level: 1 })).toBeVisible();
  await main.getByRole('link', { name: 'Register farmer', exact: true }).first().click();

  await expect(page).toHaveURL(/\/register\/new$/);
  await expect(
    main.getByRole('heading', { name: 'Register farmer', exact: true, level: 1 }),
  ).toBeVisible();
  // Cotton is the default programme, and the country chip states the consequence.
  await expect(main.getByText('Pakistan').first()).toBeVisible();

  const idField = main.getByLabel(/^CNIC/);
  await idField.fill(cnic);
  // The mask keeps the formatting the officer reads.
  await expect(idField).toHaveValue(cnic);

  // The SAWIE ID chip appears once the lookup answers, as a preview only.
  const chip = main.getByText('Assigned on save');
  await expect(chip).toBeVisible({ timeout: 15_000 });
  const previewText = await main.locator('.mono-id', { hasText: /^\d{4,}$/ }).first().innerText();
  expect(previewText).toMatch(/^\d{4,}$/);

  await main.getByLabel(/^Name/).fill('Muhammad Imran');
  await main.getByLabel(/^Father name/).fill('Ghulam Rasool');
  await main.getByLabel(/^Phone/).fill('03001234567');

  // The cascade: each level only offers options once the one above it is chosen.
  const comboboxes = main.getByRole('combobox');
  const province = comboboxes.nth(0);
  await expect(province).toBeEnabled();
  await province.selectOption({ label: 'Punjab' });

  const district = comboboxes.nth(1);
  await expect(district).toBeEnabled();
  await district.selectOption({ label: 'Multan' });

  const tehsil = comboboxes.nth(2);
  await expect(tehsil).toBeEnabled();
  await tehsil.selectOption({ label: 'Multan City' });

  await main.getByRole('combobox', { name: /Village or town/ }).fill('Basti Malook');

  // Crop details for this season.
  await main.getByLabel(/^Variety/).selectOption({ index: 1 });
  await main.getByLabel(/^Previous crop/).selectOption({ index: 1 });
  // Targeted by its group: the crop switch is a radiogroup too, so an unscoped
  // radio query would click Cotton again and leave tenure unset.
  await main.getByRole('radiogroup', { name: 'Land tenure' }).getByRole('radio').first().click();

  await main.getByRole('button', { name: 'Register farmer', exact: true }).click();

  /* ----------------------------------------------------------------- success */

  await expect(main.getByText('Farmer registered')).toBeVisible({ timeout: 20_000 });
  await expect(main.getByText('Muhammad Imran')).toBeVisible();
  const sawieId = (await main.locator('.mono-id').first().innerText()).trim();
  expect(sawieId).toMatch(/^\d{4,}$/);

  /* ------------------------------------------------------------ first field */

  await main.getByRole('button', { name: 'Add field' }).click();
  await expect(main.getByRole('button', { name: 'Draw polygon' })).toBeVisible({
    timeout: 20_000,
  });
  // The field ID is reserved and shown before anything is drawn.
  // Shown both in the header chip and in the rail, so take the first match.
  await expect(main.getByText(`${sawieId}-01`).first()).toBeVisible();
  await expect(main.getByText('Nothing drawn')).toBeVisible();

  await drawSquare(page, { dx: -150 });

  // The server measures the boundary and confirms there is no overlap; only then
  // does Save become available.
  await expect(main.getByText('No overlap')).toBeVisible({ timeout: 20_000 });
  const saveField = main.getByRole('button', { name: 'Save field' });
  await expect(saveField).toBeEnabled();
  await saveField.click();

  // The banner names the field it saved, so assert on the action it offers next.
  await expect(main.getByRole('button', { name: 'Add other field' })).toBeVisible({
    timeout: 20_000,
  });
  await expect(main.getByText(new RegExp(`Field\\s+${sawieId}-01\\s+saved`)).first()).toBeVisible();

  /* ----------------------------------------------------------- second field */

  await main.getByRole('button', { name: 'Add other field' }).click();
  // The next field for the same farmer takes the next number in their sequence.
  await expect(main.getByText(`${sawieId}-02`).first()).toBeVisible({ timeout: 20_000 });

  await drawSquare(page, { dx: 150 });

  await expect(main.getByText('No overlap')).toBeVisible({ timeout: 20_000 });
  await main.getByRole('button', { name: 'Save field' }).click();
  await expect(main.getByText(new RegExp(`Field\\s+${sawieId}-02\\s+saved`)).first()).toBeVisible({
    timeout: 20_000,
  });

  // Both fields are now listed for this farmer, with their own IDs.
  const table = main.getByRole('table', { name: /Fields mapped for this farmer/ }).first();
  await expect(table.getByText(`${sawieId}-01`)).toBeVisible();
  await expect(table.getByText(`${sawieId}-02`)).toBeVisible();
});
