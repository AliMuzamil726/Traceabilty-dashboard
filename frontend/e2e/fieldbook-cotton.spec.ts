import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

/**
 * The smoke test for Module 3: a cotton farmer's fieldbook, filled in through every one
 * of its 10 steps, submitted, and then shown read only.
 *
 * The farmer and the field are set up through Module 2's API (the map is Module 2's own
 * smoke test), on fresh ground each run so repeat runs never overlap. Everything after
 * that goes through the screen: the selection dialog's deep link, schema-driven forms,
 * repeatable entries, conditional fields, the submit confirmation and the locked view.
 */

const API = 'http://127.0.0.1:8000/api/v1';

const day = (daysAgo: number) => {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - daysAgo);
  return d.toISOString().slice(0, 10);
};

function square(lat: number, lng: number, sideM = 200) {
  const dLat = sideM / 2 / 111_320;
  const dLng = sideM / 2 / (111_320 * Math.cos((lat * Math.PI) / 180));
  const [w, e, s, n] = [lng - dLng, lng + dLng, lat - dLat, lat + dLat];
  return { type: 'Polygon', coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] };
}

async function makeCottonFarm(request: APIRequestContext) {
  const offices = await (await request.get(`${API}/offices`, { params: { country: 'PK' } })).json();
  const seven = String(Date.now()).slice(-7);
  const farmerRes = await request.post(`${API}/register/farmers`, {
    data: {
      crop: 'cotton', id_number: `35202-${seven}-3`, name: 'fieldbook smoke', father_name: 'test father',
      phone: '0300-1234567', province_code: 'PK-PB', district_code: 'PK-PB-MUL', tehsil_code: 'PK-PB-MUL-T01',
      village: 'Basti Malook', field_office_id: offices.items[0].id, variety: 'fh-142', tenure: 'owner', previous_crop: 'wheat',
    },
  });
  expect(farmerRes.ok(), await farmerRes.text()).toBeTruthy();
  const farmer = (await farmerRes.json()).farmer;
  const fieldRes = await request.post(`${API}/register/farmers/${farmer.id}/fields`, {
    data: { geometry: square(29 + Math.random() * 2, 71 + Math.random() * 3) },
  });
  expect(fieldRes.ok(), await fieldRes.text()).toBeTruthy();
  return { farmer, field: await fieldRes.json() };
}

type Answer = string | number | string[];

/** Fill one schema field by its key, whatever control the schema chose for it. */
async function answer(page: Page, key: string, value: Answer) {
  const box = page.locator(`[data-field="${key}"]`).last();
  await expect(box).toBeVisible();
  if (Array.isArray(value)) {
    for (const v of value) await box.locator(`input[type="checkbox"][value="${v}"], label:has-text("${v}") input`).first().check();
    return;
  }
  const select = box.locator('select');
  if ((await select.count()) > 0) {
    await expect(select.locator(`option[value="${value}"]`)).toHaveCount(1);
    await select.selectOption(String(value));
    return;
  }
  const radio = box.locator(`input[type="radio"][value="${value}"]`);
  if ((await radio.count()) > 0) {
    await radio.check();
    return;
  }
  await box.locator('input').first().fill(String(value));
}

async function answerAll(page: Page, values: Record<string, Answer>) {
  for (const [key, value] of Object.entries(values)) await answer(page, key, value);
}

async function nextStep(page: Page, title: string) {
  await page.getByRole('button', { name: 'Save and Next' }).click();
  await expect(page.getByRole('heading', { name: title, level: 2 })).toBeVisible();
}

/** A repeatable step opens on a new entry when empty; fill it and save the entry. */
async function addEntry(page: Page, values: Record<string, Answer>) {
  await answerAll(page, values);
  await page.getByRole('button', { name: 'Save entry' }).click();
  await expect(page.getByText('Entry saved').first()).toBeVisible();
  await expect(page.getByRole('button', { name: /^Entry 1/ })).toBeVisible();
}

test('a cotton fieldbook is filled in, submitted and locked', async ({ page, request }) => {
  const { farmer, field } = await makeCottonFarm(request);

  // Deep link from a farmer profile: farmer and field arrive preselected.
  await page.goto(`/fieldbook?farmerId=${farmer.id}&fieldId=${field.id}`);
  const dialog = page.getByRole('dialog', { name: 'Open a fieldbook' });
  await expect(dialog.getByRole('radio', { name: new RegExp(field.field_id) })).toHaveAttribute('aria-checked', 'true');
  await dialog.getByRole('button', { name: 'Open fieldbook' }).click();
  await expect(page.getByRole('heading', { name: 'Field info', level: 2 })).toBeVisible();

  // 1. Field info: area sown starts from the mapped area.
  await expect(page.locator('[data-field="area_sown"] input')).not.toHaveValue('');
  await answerAll(page, { crop_season: 'kharif', area_sown: 9.5, soil_texture: 'loam', drainage_status: 'well_drained' });
  await nextStep(page, 'Land preparation');

  // 2. Land preparation (repeatable).
  await addEntry(page, {
    operation_date: day(160), operation_type: 'deep_ploughing', machinery_type: 'tractor_owned', passes: 2,
    tillage_depth: 25, area_covered: 9.5, diesel_per_pass: 6, residue_handling: 'incorporated', cover_crop: 'none',
  });
  await nextStep(page, 'Sowing');

  // 3. Sowing: the variety comes from registration.
  await expect(page.locator('[data-field="variety"] select')).toHaveValue('fh-142');
  await answerAll(page, {
    sowing_date: day(150), seed_source: 'registered_dealer', seed_rate: 8, sowing_method: 'bed_and_furrow',
    sowing_equipment: 'seed_drill', plant_population: 22000,
  });
  await nextStep(page, 'Nutrient management');
  await expect(page.getByLabel('Crop clock')).toContainText('Day 150');

  // 4. Nutrient management: the typical analysis is offered for the product.
  await answerAll(page, { application_date: day(140), product: 'urea' });
  await page.getByRole('button', { name: /Use typical value: 46/ }).click();
  await addEntry(page, { quantity: 50, crop_stage: 'seedling' });
  await nextStep(page, 'Irrigation');

  // 5. Irrigation: diesel appears only for a diesel tubewell.
  await answerAll(page, { irrigation_date: day(130), source: 'tubewell_diesel' });
  await expect(page.locator('[data-field="diesel_used"]')).toBeVisible();
  await addEntry(page, { method: 'furrow', duration: 6, water_applied: 75, diesel_used: 20, pumping_head: 18, pump_efficiency: 55 });
  await nextStep(page, 'Weed management');

  // 6. Weed management.
  await addEntry(page, { weed_date: day(120), method: 'manual_weeding' });
  await nextStep(page, 'Pest and disease (IPM)');

  // 7. Pest and disease: nothing to record this season.
  // The box follows the saved state, so it ticks once the server has answered.
  await page.getByLabel('Nothing to record for this step').click();
  await expect(page.getByLabel('Nothing to record for this step')).toBeChecked();
  await expect(page.getByText('Marked as nothing to record.')).toBeVisible();
  await nextStep(page, 'Energy');

  // 8. Energy.
  await answerAll(page, { total_diesel: 180, grid_electricity: 0 });
  await nextStep(page, 'Labour and social');

  // 9. Labour and social.
  await answerAll(page, { family_labour: 3, hired_labour: 10, women_pickers: 8, picking_wage: 1200, training_attended: 'yes' });
  await answer(page, 'training_name', 'Better Cotton field school');
  await nextStep(page, 'Harvest');

  // 10. Harvest: one picking, ready for pickup.
  await addEntry(page, {
    picking_date: day(20), picking_number: '1st', harvest_method: 'manual_picking', yield: 12, moisture: 9,
    storage_material: 'cotton_cloth', ready_for_pickup: 'yes',
  });

  // The last step submits, through a confirmation.
  await expect(page.getByRole('button', { name: 'Save and Next' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Save and Submit' }).click();
  const confirm = page.getByRole('alertdialog', { name: 'Submit this fieldbook?' });
  await expect(confirm).toBeVisible();
  await confirm.getByRole('button', { name: 'Submit and lock' }).click();

  // Read only from here on.
  await expect(page).toHaveURL(/\/fieldbook\/books\/[^/]+\/view$/);
  await expect(page.getByText('This fieldbook is submitted and locked. It is read only.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save and Next' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Save entry' })).toHaveCount(0);
  await expect(page.locator('main input:not([type="hidden"])')).toHaveCount(0);
  await expect(page.getByText('Better Cotton field school')).toBeVisible();

  // The editor route sends a locked book back to the summary.
  const viewUrl = page.url();
  await page.goto(viewUrl.replace(/\/view$/, ''));
  await expect(page).toHaveURL(/\/view$/);
});
