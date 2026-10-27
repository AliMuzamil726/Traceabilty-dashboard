import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/renderWithProviders';
import { TEHSIL_OTHER } from '../api/schemas';
import { LocationCascade, type LocationValue } from '../components/LocationCascade';

const PROVINCES = {
  items: [
    { value: 'PK-PB', label: 'Punjab', level: 'province', parent_code: null },
    { value: 'PK-SD', label: 'Sindh', level: 'province', parent_code: null },
  ],
  allow_manual: false,
};

const DISTRICTS: Record<string, unknown> = {
  'PK-PB': {
    items: [
      { value: 'PK-PB-MUL', label: 'Multan', level: 'district', parent_code: 'PK-PB' },
      { value: 'PK-PB-LHR', label: 'Lahore', level: 'district', parent_code: 'PK-PB' },
    ],
    allow_manual: false,
  },
  'PK-SD': {
    items: [{ value: 'PK-SD-SAN', label: 'Sanghar', level: 'district', parent_code: 'PK-SD' }],
    allow_manual: false,
  },
};

const TEHSILS: Record<string, unknown> = {
  'PK-PB-MUL': {
    items: [
      { value: 'PK-PB-MUL-T01', label: 'Multan City', level: 'tehsil', parent_code: 'PK-PB-MUL' },
      { value: 'PK-PB-MUL-T02', label: 'Shujabad', level: 'tehsil', parent_code: 'PK-PB-MUL' },
    ],
    allow_manual: true,
  },
  // Lahore has no seeded tehsils, so the form must still offer manual entry.
  'PK-PB-LHR': { items: [], allow_manual: true },
  'PK-SD-SAN': {
    items: [
      { value: 'PK-SD-SAN-T01', label: 'Shahdadpur', level: 'tehsil', parent_code: 'PK-SD-SAN' },
    ],
    allow_manual: true,
  },
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const url = new URL(String(input), 'http://localhost');
      const path = url.pathname;
      if (path.endsWith('/locations/provinces')) return Promise.resolve(jsonResponse(PROVINCES));
      if (path.endsWith('/locations/districts')) {
        const province = url.searchParams.get('province') ?? '';
        return Promise.resolve(jsonResponse(DISTRICTS[province] ?? { items: [], allow_manual: false }));
      }
      if (path.endsWith('/locations/tehsils')) {
        const district = url.searchParams.get('district') ?? '';
        return Promise.resolve(jsonResponse(TEHSILS[district] ?? { items: [], allow_manual: true }));
      }
      if (path.endsWith('/villages/suggest')) {
        return Promise.resolve(jsonResponse(['Basti Malook', 'Basti Nau']));
      }
      return Promise.resolve(jsonResponse({}));
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** The cascade is controlled, so the test holds the state the form would hold. */
function Harness({ onChange }: { onChange?: (value: LocationValue) => void } = {}) {
  const [value, setValue] = useState<LocationValue>({
    province_code: '',
    district_code: '',
    tehsil_code: '',
    tehsil_name: '',
    village: '',
  });
  return (
    <LocationCascade
      country="PK"
      value={value}
      onChange={(next) => {
        setValue(next);
        onChange?.(next);
      }}
    />
  );
}

// Queried by role and position rather than by label text: a required FormField label
// also contains the asterisk and the "(required)" hint, so an exact label match fails.
const selects = () => screen.getAllByRole('combobox');
const provinceSelect = () => selects()[0] as HTMLSelectElement;
const districtSelect = () => selects()[1] as HTMLSelectElement;
const tehsilSelect = () => selects()[2] as HTMLSelectElement;
// An input with a datalist is a combobox per ARIA, not a textbox.
const villageInput = () =>
  screen.getByRole('combobox', { name: /Village or town/ }) as HTMLInputElement;

describe('LocationCascade', () => {
  it('loads provinces and leaves the levels below disabled', async () => {
    renderWithProviders(<Harness />);
    await waitFor(() => expect(provinceSelect()).not.toBeDisabled());

    expect(await screen.findByRole('option', { name: 'Punjab' })).toBeInTheDocument();
    expect(districtSelect()).toBeDisabled();
    expect(tehsilSelect()).toBeDisabled();
    expect(villageInput()).toBeDisabled();
  });

  it('enables each level only once the level above it is chosen', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness />);
    await screen.findByRole('option', { name: 'Punjab' });

    await user.selectOptions(provinceSelect(), 'PK-PB');
    await waitFor(() => expect(districtSelect()).not.toBeDisabled());
    expect(await screen.findByRole('option', { name: 'Multan' })).toBeInTheDocument();
    expect(tehsilSelect()).toBeDisabled();

    await user.selectOptions(districtSelect(), 'PK-PB-MUL');
    await waitFor(() => expect(tehsilSelect()).not.toBeDisabled());
    expect(await screen.findByRole('option', { name: 'Multan City' })).toBeInTheDocument();
  });

  it('clears the district, tehsil and village when the province changes', async () => {
    const user = userEvent.setup();
    const changes: LocationValue[] = [];
    renderWithProviders(<Harness onChange={(value) => changes.push(value)} />);
    await screen.findByRole('option', { name: 'Punjab' });

    await user.selectOptions(provinceSelect(), 'PK-PB');
    await screen.findByRole('option', { name: 'Multan' });
    await user.selectOptions(districtSelect(), 'PK-PB-MUL');
    await screen.findByRole('option', { name: 'Multan City' });
    await user.selectOptions(tehsilSelect(), 'PK-PB-MUL-T01');
    await waitFor(() => expect(villageInput()).not.toBeDisabled());
    await user.type(villageInput(), 'Basti Malook');

    // Switching province must not leave Multan selected under Sindh.
    await user.selectOptions(provinceSelect(), 'PK-SD');

    const latest = changes[changes.length - 1]!;
    expect(latest.province_code).toBe('PK-SD');
    expect(latest.district_code).toBe('');
    expect(latest.tehsil_code).toBe('');
    expect(latest.tehsil_name).toBe('');
    expect(latest.village).toBe('');

    await waitFor(() => expect(districtSelect()).toHaveValue(''));
    expect(tehsilSelect()).toBeDisabled();
  });

  it('clears the tehsil and village when the district changes', async () => {
    const user = userEvent.setup();
    const changes: LocationValue[] = [];
    renderWithProviders(<Harness onChange={(value) => changes.push(value)} />);
    await screen.findByRole('option', { name: 'Punjab' });

    await user.selectOptions(provinceSelect(), 'PK-PB');
    await screen.findByRole('option', { name: 'Multan' });
    await user.selectOptions(districtSelect(), 'PK-PB-MUL');
    await screen.findByRole('option', { name: 'Multan City' });
    await user.selectOptions(tehsilSelect(), 'PK-PB-MUL-T02');

    await user.selectOptions(districtSelect(), 'PK-PB-LHR');

    const latest = changes[changes.length - 1]!;
    expect(latest.province_code).toBe('PK-PB');
    expect(latest.district_code).toBe('PK-PB-LHR');
    expect(latest.tehsil_code).toBe('');
    expect(latest.village).toBe('');
  });

  it('offers Other (type manually) even for a district with tehsils', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness />);
    await screen.findByRole('option', { name: 'Punjab' });
    await user.selectOptions(provinceSelect(), 'PK-PB');
    await screen.findByRole('option', { name: 'Multan' });
    await user.selectOptions(districtSelect(), 'PK-PB-MUL');

    expect(
      await screen.findByRole('option', { name: 'Other (type manually)' }),
    ).toBeInTheDocument();
  });

  it('offers manual entry for a district with no seeded tehsils', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness />);
    await screen.findByRole('option', { name: 'Punjab' });
    await user.selectOptions(provinceSelect(), 'PK-PB');
    await screen.findByRole('option', { name: 'Lahore' });
    await user.selectOptions(districtSelect(), 'PK-PB-LHR');

    await waitFor(() => expect(tehsilSelect()).not.toBeDisabled());
    expect(screen.queryByRole('option', { name: 'Multan City' })).not.toBeInTheDocument();
    expect(
      await screen.findByRole('option', { name: 'Other (type manually)' }),
    ).toBeInTheDocument();
  });

  it('shows a text field for the tehsil name when Other is chosen', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness />);
    await screen.findByRole('option', { name: 'Punjab' });
    await user.selectOptions(provinceSelect(), 'PK-PB');
    await screen.findByRole('option', { name: 'Multan' });
    await user.selectOptions(districtSelect(), 'PK-PB-MUL');
    await screen.findByRole('option', { name: 'Other (type manually)' });
    await user.selectOptions(tehsilSelect(), TEHSIL_OTHER);

    const typed = await screen.findByLabelText(/Tehsil or city name/);
    await user.type(typed, 'New Tehsil');
    expect(typed).toHaveValue('New Tehsil');
  });

  it('lets a village be typed freely and suggests the ones already entered', async () => {
    const user = userEvent.setup();
    const changes: LocationValue[] = [];
    renderWithProviders(<Harness onChange={(value) => changes.push(value)} />);
    await screen.findByRole('option', { name: 'Punjab' });
    await user.selectOptions(provinceSelect(), 'PK-PB');
    await screen.findByRole('option', { name: 'Multan' });
    await user.selectOptions(districtSelect(), 'PK-PB-MUL');
    await screen.findByRole('option', { name: 'Multan City' });
    await user.selectOptions(tehsilSelect(), 'PK-PB-MUL-T01');
    await waitFor(() => expect(villageInput()).not.toBeDisabled());

    // A village nobody has entered before must still be typeable.
    await user.type(villageInput(), 'Chak 42');
    expect(changes[changes.length - 1]!.village).toBe('Chak 42');

    const list = villageInput().getAttribute('list');
    expect(list).toBeTruthy();
    await waitFor(() => {
      const datalist = document.getElementById(list as string);
      expect(datalist?.querySelectorAll('option').length).toBeGreaterThan(0);
    });
  });
});
