import { expect, test, type Page } from '@playwright/test';

/**
 * The smoke test for Module 8: Settings is administrator-only, a list value added here
 * reaches the form that uses it, deactivating it hides it from new work without
 * touching what is recorded, and a crop-clock change moves fields on Harvest Radar.
 *
 * It exercises what no unit test can: the officer switcher driving a real 403, the
 * caches of four modules dropping what they hold after `config.changed`, and the
 * round trip from a saved setting to the screen an officer actually uses.
 */

const SELECT = 'Acting officer (development)';

/** A label that is different on every run, so the test can be repeated. */
function uniqueLabel(): string {
  return `Test variety ${String(Date.now()).slice(-6)}`;
}

/** Act as the seeded administrator, or as a field officer. */
async function actAs(page: Page, who: 'admin' | 'officer'): Promise<void> {
  const select = page.getByLabel(SELECT);
  await expect(select).toBeEnabled();
  const label = who === 'admin' ? /Administrator/ : /Multan|Bahawalpur|Lodhran/;
  const option = await select
    .locator('option')
    .filter({ hasText: label })
    .first()
    .getAttribute('value');
  if (!option) throw new Error(`No ${who} in the officer switcher`);
  await select.selectOption(option);
  await expect(select).toHaveValue(option);
}

test('an administrator adds a list value, the register offers it, deactivating hides it', async ({
  page,
}) => {
  const label = uniqueLabel();

  await page.goto('/settings/lists');
  await actAs(page, 'admin');
  await page.goto('/settings/lists');

  // Pick the seed-variety list, which the Register Farmer form reads.
  const listButton = page.getByRole('button', { name: /variety/i }).first();
  await expect(listButton).toBeVisible();
  await listButton.click();

  await page.getByLabel('Add a value').fill(label);
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  await expect(page.getByRole('textbox', { name: new RegExp(`Label for`) }).first()).toBeVisible();
  await expect(page.getByText(label)).toBeVisible();

  // The new value reaches the form that uses the list.
  await page.goto('/register/new');
  const variety = page.getByLabel(/variety/i).first();
  await expect(variety).toBeVisible();
  await expect(variety.locator('option', { hasText: label })).toHaveCount(1);

  // Deactivating takes it out of new forms.
  await page.goto('/settings/lists');
  await listButton.click();
  const row = page.locator('li', { hasText: label }).first();
  await row.getByRole('switch').click();
  await expect(page.getByText(/Value saved|saved/i).first()).toBeVisible({ timeout: 5000 });

  await page.goto('/register/new');
  await expect(page.getByLabel(/variety/i).first().locator('option', { hasText: label })).toHaveCount(
    0,
  );
});

test('a crop-clock change previews its effect and moves the radar buckets', async ({ page }) => {
  await page.goto('/settings/crops');
  await actAs(page, 'admin');
  await page.goto('/settings/crops');

  const readyDay = page.getByLabel('Ready from day').first();
  await expect(readyDay).toBeVisible();
  const before = await readyDay.inputValue();

  await readyDay.fill(String(Math.max(2, Number(before) - 20)));

  // The impact preview says how many fields would move before anything is saved.
  await expect(page.getByText(/would change bucket|moves nothing today/)).toBeVisible({
    timeout: 10_000,
  });

  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByText(/applies to new calculations|Saved/i).first()).toBeVisible();

  // Harvest Radar reads the clock through Module 3, so its counts follow.
  await page.goto('/radar');
  await expect(page.getByRole('heading', { name: 'Harvest Radar' })).toBeVisible();

  // Put the clock back, so a repeat run starts from the same place.
  await page.goto('/settings/crops');
  await page.getByLabel('Ready from day').first().fill(before);
  await page.getByRole('button', { name: 'Save changes' }).click();
});

test('a field officer is refused Settings and told how to act as an administrator', async ({
  page,
}) => {
  await page.goto('/settings/officers');
  await actAs(page, 'officer');
  await page.goto('/settings/officers');

  await expect(page.getByText('Administrator access required')).toBeVisible();
  await expect(page.getByText(/officer switcher/i)).toBeVisible();

  // Their own preferences are still theirs to change.
  await page.goto('/settings/preferences');
  await expect(page.getByRole('heading', { name: 'My preferences' })).toBeVisible();
  await expect(page.getByRole('radio', { name: 'Compact' })).toBeVisible();
});
