import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MotionConfig } from 'framer-motion';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Book, StepState } from '../api/types';
import { FormStepper } from '../components/FormStepper';
import FieldbookEditorPage from '../pages/FieldbookEditorPage';
import { useDraftStore } from '../store/draftStore';
import { cotton, mockMasterLists } from './fixtures';

function makeBook(statuses: Record<string, StepState['status']> = {}): Book {
  return {
    id: 'b1', field_id: 'f1', field_code: '1001-01', farmer_id: 'fa1', crop: 'cotton', season_year: 2026,
    status: 'draft', locked: false, current_step: 'field_info', schema_version: '2026.1', version: 3,
    created_at: '2026-05-01T00:00:00Z', updated_at: '2026-05-01T00:00:00Z', created_by: null,
    submitted_at: null, submitted_by: null, ready_for_pickup_at: null,
    farmer: { id: 'fa1', sawie_id: 1001, name: 'Muhammad Imran', crop: 'cotton', country: 'PK', registered_by: null, home_office_licence_no: null },
    field: { id: 'f1', field_id: '1001-01', area_acre: 9.88, area_ha: 4 },
    defaults: { 'field.area_acre': 9.88, 'season.variety': 'fh-142' },
    steps: cotton.steps.map((s) => ({ key: s.key, status: statuses[s.key] ?? 'not_started', entry_count: 0, entries: [] })),
    photos: [], warnings: [], errors: [], missing_steps: [],
    crop_clock: { crop: 'cotton', approach_day: 120, ready_day: 135, window_end_day: 200 },
    crop_status: { status: 'no_sowing_data', label: 'No sowing date', days_after_sowing: null, sowing_date: null, overdue: false, next_milestone: 'Record the sowing date to start the crop clock.' },
  };
}

let fetchSpy: ReturnType<typeof mockMasterLists>;
beforeEach(() => {
  useDraftStore.setState({ drafts: {} });
  const master = mockMasterLists();
  const masterImpl = master.getMockImplementation()!;
  fetchSpy = master.mockImplementation(async (input, init) => {
    const path = new URL(String(input), 'http://test').pathname;
    const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
    if (path.endsWith('/schemas/cotton')) return json(cotton);
    if (path.endsWith('/timeline')) return json({ items: [] });
    if (path.endsWith('/books/b1')) return json(makeBook());
    return masterImpl(input, init);
  });
});
afterEach(() => fetchSpy.mockRestore());

function renderEditor(step: string) {
  const router = createMemoryRouter([{ path: '/fieldbook/books/:bookId', element: <FieldbookEditorPage /> }], {
    initialEntries: [`/fieldbook/books/b1?step=${step}`],
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MotionConfig reducedMotion="always">
        <RouterProvider router={router} />
      </MotionConfig>
    </QueryClientProvider>,
  );
}

describe('FormStepper', () => {
  it('marks each step by its own state, not its position', () => {
    // The compact (mobile) and full (desktop) lists both render; CSS shows one.
    const book = makeBook({ sowing: 'complete', harvest: 'complete', pest_disease: 'not_applicable' });
    render(<FormStepper steps={cotton.steps} states={book.steps} current="field_info" onSelect={vi.fn()} />);
    const nav = screen.getByRole('navigation', { name: 'Fieldbook steps' });
    expect(within(nav).getAllByRole('button', { name: /Sowing,? complete/ }).length).toBeGreaterThan(0);
    expect(within(nav).getAllByRole('button', { name: /Harvest,? complete/ }).length).toBeGreaterThan(0);
    expect(within(nav).getAllByRole('button', { name: /Pest and disease.*nothing to record/i }).length).toBeGreaterThan(0);
    expect(within(nav).getAllByRole('button', { name: /Irrigation,? not started/ }).length).toBeGreaterThan(0);
    const bars = within(nav).getAllByRole('progressbar');
    expect(bars.length).toBeGreaterThan(0);
    for (const bar of bars) expect(bar).toHaveAttribute('aria-valuenow', '3');
  });

  it('lets the officer jump to any step', async () => {
    const onSelect = vi.fn();
    render(<FormStepper steps={cotton.steps} states={makeBook().steps} current="field_info" onSelect={onSelect} />);
    await userEvent.click(screen.getAllByRole('button', { name: /^Energy/ })[0]!);
    expect(onSelect).toHaveBeenCalledWith('energy');
  });
});

describe('editor buttons', () => {
  it('offers Save and Next on every step but the last', async () => {
    renderEditor('field_info');
    expect(await screen.findByRole('heading', { name: 'Field info' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save and Next' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save and Submit' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Back' })).toBeDisabled();
  });

  it('offers Save and Submit only on the last step', async () => {
    renderEditor('transport');
    expect(await screen.findByText(/Step 11 of 11/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save and Submit' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save and Next' })).toBeNull();
  });

  it('stops Save and Next on missing required answers without calling the server', async () => {
    const user = userEvent.setup();
    renderEditor('energy');
    await user.click(await screen.findByRole('button', { name: 'Save and Next' }));
    expect(await screen.findAllByText('Answer this question.')).not.toHaveLength(0);
    expect(fetchSpy.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === 'PUT')).toBe(false);
  });
});
