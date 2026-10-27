import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MotionConfig } from 'framer-motion';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';
import RadarPage from '../pages/RadarPage';
import { page, row } from './fixtures';

let fetchSpy: MockInstance<typeof fetch>;
const calls = () => fetchSpy.mock.calls.map(([input]) => new URL(String(input), 'http://test'));
const lastFieldsCall = () => [...calls()].reverse().find((u) => u.pathname.endsWith('/radar/fields'));

function json(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
}

// Recharts measures its container; jsdom has no ResizeObserver.
class NoResize {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', NoResize);
  fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://test');
    if (url.pathname.endsWith('/radar/calendar')) {
      return json({ month: url.searchParams.get('month'), days: [{ date: `${url.searchParams.get('month')}-14`, fields: 3, estimated_kg: 2400 }], weeks: [] });
    }
    const status = url.searchParams.get('status');
    const items = [row(), row({ field_id: 'f2', field_code: '1002-01', status: 'growing', can_request: false })];
    return json(page(status ? items.filter((r) => r.status === status) : items));
  });
});
afterEach(() => {
  fetchSpy.mockRestore();
  vi.unstubAllGlobals();
});

function Location() {
  const loc = useLocation();
  return <output data-testid="location">{loc.search}</output>;
}

function renderPage(search = '') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MotionConfig reducedMotion="always">
        <MemoryRouter initialEntries={[`/radar${search}`]}>
          <RadarPage />
          <Location />
        </MemoryRouter>
      </MotionConfig>
    </QueryClientProvider>,
  );
}

describe('RadarPage', () => {
  it('filters by bucket, highlights it, and keeps it in the URL', async () => {
    const user = userEvent.setup();
    renderPage();
    const buckets = await screen.findByRole('group', { name: 'Filter by status' });
    const ready = await within(buckets).findByRole('button', { name: /Ready\s*4/ });
    expect(ready).toHaveAttribute('aria-pressed', 'false');
    await user.click(ready);
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('status=ready'));
    expect(within(buckets).getByRole('button', { name: /Ready\s*4/ })).toHaveAttribute('aria-pressed', 'true');
    await waitFor(() => expect(lastFieldsCall()?.searchParams.get('status')).toBe('ready'));
    await waitFor(() => expect(screen.queryByText('1002-01')).toBeNull());
    // Clicking the active bucket again shows every bucket.
    await user.click(within(buckets).getByRole('button', { name: /Ready\s*4/ }));
    await waitFor(() => expect(screen.getByTestId('location')).not.toHaveTextContent('status='));
  });

  it('starts from filters in the URL and sends them to the API', async () => {
    renderPage('?crop=cotton&district=Multan&tehsil=Multan%20City&q=imran&scope=all&sort=-das');
    await screen.findByText('1001-01');
    const call = lastFieldsCall();
    expect(call?.searchParams.get('district')).toBe('Multan');
    expect(call?.searchParams.get('tehsil')).toBe('Multan City');
    expect(call?.searchParams.get('q')).toBe('imran');
    expect(call?.searchParams.get('scope')).toBe('all');
    expect(call?.searchParams.get('sort')).toBe('-das');
    expect(screen.getByText('3 filters')).toBeInTheDocument();
  });

  it('clears child locations when the district changes, and clears all filters', async () => {
    const user = userEvent.setup();
    renderPage('?district=Multan&tehsil=Multan%20City&village=Basti%20Malook');
    await screen.findByText('1001-01');
    await user.selectOptions(screen.getByLabelText('District'), 'Bahawalpur');
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('district=Bahawalpur'));
    expect(screen.getByTestId('location')).not.toHaveTextContent('tehsil');
    await user.click(screen.getByRole('button', { name: 'Clear filters' }));
    await waitFor(() => expect(screen.getByTestId('location')).not.toHaveTextContent('district'));
  });

  it('enables Request pickup only for an eligible selection', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('1001-01');
    await user.click(screen.getByRole('checkbox', { name: 'Select row f1' }));
    const bar = await screen.findByRole('region', { name: 'Selected fields' });
    expect(within(bar).getByRole('button', { name: 'Request pickup' })).not.toHaveAttribute('aria-disabled');
    await user.click(screen.getByRole('checkbox', { name: 'Select row f2' }));
    const button = within(bar).getByRole('button', { name: 'Request pickup' });
    expect(button).toHaveAttribute('aria-disabled', 'true');
    expect(document.getElementById('request-blockers')).toHaveTextContent('Not ready or harvested: 1002-01');
    await user.click(button);
    expect(screen.queryByRole('dialog', { name: 'Request pickup' })).toBeNull();
    await user.click(screen.getByRole('checkbox', { name: 'Select row f2' }));
    await user.click(within(bar).getByRole('button', { name: 'Request pickup' }));
    expect(await screen.findByRole('dialog', { name: 'Request pickup' })).toBeInTheDocument();
  });

  it('filters the table to a calendar day', async () => {
    const user = userEvent.setup();
    renderPage('?view=calendar&month=2026-10');
    const day = await screen.findByRole('gridcell', { name: /2026-10-14: 3 fields/ });
    await user.click(day);
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('from=2026-10-14'));
    expect(screen.getByTestId('location')).toHaveTextContent('to=2026-10-14');
    expect(screen.getByTestId('location')).toHaveTextContent('view=table');
    await waitFor(() => expect(lastFieldsCall()?.searchParams.get('ready_from')).toBe('2026-10-14'));
    expect(lastFieldsCall()?.searchParams.get('ready_to')).toBe('2026-10-14');
  });
});
