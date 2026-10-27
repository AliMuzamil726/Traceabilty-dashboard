import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MotionConfig } from 'framer-motion';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';
import { PipelineTracker } from '../components/PipelineTracker';
import DashboardPage from '../pages/DashboardPage';
import * as fx from './fixtures';

let fetchSpy: MockInstance<typeof fetch>;
let failing = new Set<string>();
let answers: Record<string, unknown> = {};

const calls = () => fetchSpy.mock.calls.map(([input]) => new URL(String(input), 'http://test'));

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

class NoResize {
  observe() {}
  unobserve() {}
  disconnect() {}
}

function defaults(): Record<string, unknown> {
  return {
    overview: fx.overview(),
    pipeline: fx.pipeline,
    distribution: fx.distribution(),
    alerts: fx.alerts(),
    activity: fx.activity,
    map: fx.emptyMap,
    onboarding: fx.onboarding(false),
    // The programme dashboard is what an administrator and staff see; a field officer
    // gets their own screen, tested separately below.
    me: { id: 'a1', code: 'ADMIN-01', full_name: 'Aiman Aziz', role: 'admin', country: 'PK', field_office_id: null, field_office_name: null, email: null, phone: null, has_photo: false, is_admin: true, sees_all: true },
  };
}

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', NoResize);
  failing = new Set();
  answers = defaults();
  fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://test');
    if (url.pathname.endsWith('/officers/me')) return json(answers.me);
    const section = url.pathname.split('/dashboard/')[1] ?? '';
    if (failing.has(section)) {
      return json({ error: { code: 'internal_error', message: 'Something broke.', details: null } }, 500);
    }
    if (section === 'timeseries') return json(fx.series(url.searchParams.get('metric') as 'registrations'));
    return json(answers[section] ?? {});
  });
});

afterEach(() => {
  fetchSpy.mockRestore();
  vi.unstubAllGlobals();
});

function Location() {
  return <output data-testid="location">{useLocation().search}</output>;
}

function renderPage(search = '') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MotionConfig reducedMotion="always">
        <MemoryRouter initialEntries={[`/${search}`]}>
          <DashboardPage />
          <Location />
        </MemoryRouter>
      </MotionConfig>
    </QueryClientProvider>,
  );
}

describe('DashboardPage', () => {
  it('shows the title, the pipeline, KPIs and alerts', async () => {
    renderPage();
    expect(await screen.findByRole('heading', { level: 1, name: 'Home' })).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: /Harvest ready or done/ })).toHaveAttribute(
      'href',
      '/radar?crop=cotton&status=ready&season=2026',
    );
    expect(await screen.findByText('Ready for pickup now')).toBeInTheDocument();
    expect(await screen.findByText('Ready with no pickup request')).toBeInTheDocument();
  });

  it('keeps every filter in the address and sends it to every section', async () => {
    const user = userEvent.setup();
    renderPage('?crop=hemp&season=2025');
    await screen.findByText('Ready for pickup now');

    const overviewCall = calls().find((u) => u.pathname.endsWith('/dashboard/overview'))!;
    expect(overviewCall.searchParams.get('crop')).toBe('hemp');
    expect(overviewCall.searchParams.get('season_year')).toBe('2025');

    await user.click(screen.getByRole('radio', { name: 'Cotton' }));
    await waitFor(() => expect(screen.getByTestId('location').textContent).toContain('crop=cotton'));
    await user.selectOptions(screen.getByRole('combobox', { name: 'Date range' }), '7d');
    await waitFor(() => expect(screen.getByTestId('location').textContent).toContain('range=7d'));
    await waitFor(() =>
      expect(calls().some((u) => u.pathname.endsWith('/pipeline') && u.searchParams.get('range') === '7d' && u.searchParams.get('crop') === 'cotton')).toBe(true),
    );
  });

  it('shows a retry inside a failing section and keeps the rest of the page', async () => {
    failing = new Set(['alerts']);
    renderPage();

    const attention = (await screen.findByRole('heading', { name: 'Needs attention' })).closest('section')!;
    expect(await within(attention).findByRole('alert')).toHaveTextContent('could not be loaded');
    // Everything else still rendered.
    expect(await screen.findByText('Ready for pickup now')).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: /Fields mapped/ })).toBeInTheDocument();

    failing = new Set();
    await userEvent.setup().click(within(attention).getByRole('button', { name: 'Try again' }));
    expect(await within(attention).findByText('Ready with no pickup request')).toBeInTheDocument();
  });

  it('never shows the guided checklist, even on an empty database', async () => {
    answers.onboarding = fx.onboarding(true);
    renderPage();
    await screen.findByText('Ready for pickup now');
    expect(screen.queryByRole('heading', { name: 'Get started' })).toBeNull();
  });

  it('hides the checklist once the programme has data', async () => {
    renderPage();
    await screen.findByText('Ready for pickup now');
    expect(screen.queryByRole('heading', { name: 'Get started' })).toBeNull();
  });

  it('switches units and wording with the crop', async () => {
    answers.overview = fx.overview({
      crop: 'hemp',
      units: { area: 'ha', mass: 't' },
      kpis: { ...fx.overview().kpis, fields: { total: 4, area: 16, area_unit: 'ha', area_by_crop: { hemp: 16 } } },
    });
    answers.distribution = fx.distribution({
      focus_crop: 'hemp',
      area_unit: 'ha',
      region_label: 'County',
      heap_utilisation: [{ ...fx.distribution().heap_utilisation[0]!, kind: 'batch', crop: 'hemp' }],
    });
    renderPage('?crop=hemp');

    expect(await screen.findByText('16 ha')).toBeInTheDocument();
    expect(await screen.findByText(/^(2\.5|8) t, /)).toBeInTheDocument();
  });

  it('shows cotton in acres and maunds', async () => {
    renderPage('?crop=cotton');
    expect(await screen.findByText('790.4 acre')).toBeInTheDocument();
    expect(await screen.findByText(/^200 maunds, /)).toBeInTheDocument();
  });

  it('asks for the officer table as an administrator', async () => {
    renderPage();
    await screen.findByText('Ready for pickup now');
    await waitFor(() => expect(calls().some((u) => u.pathname.endsWith('/dashboard/officers'))).toBe(true));
  });

  it('gives a field officer their own screen instead', async () => {
    answers.me = { ...(answers.me as Record<string, unknown>), role: 'officer', is_admin: false, sees_all: false };
    renderPage();
    expect(await screen.findByRole('heading', { name: 'My season' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Register a farmer/ })).toHaveAttribute('href', '/register/new');
    expect(screen.queryByRole('heading', { name: 'Traceability Stages' })).toBeNull();
    expect(calls().some((u) => u.pathname.endsWith('/dashboard/officers'))).toBe(false);
  });

  it('lists only the rules that found something, critical first', async () => {
    renderPage();
    const panel = (await screen.findByRole('heading', { name: 'Needs attention' })).closest('section')!;
    await within(panel).findByText('Overdue fields');
    const titles = within(panel).getAllByRole('listitem').map((li) => li.textContent ?? '');
    const order = titles.filter((t) => /Overdue fields|Ready with no pickup/.test(t));
    expect(order[0]).toMatch(/Overdue fields/);
    expect(within(panel).queryByText('Idle heaps and batches')).toBeNull();
  });
});

describe('PipelineTracker', () => {
  function renderTracker() {
    render(
      <MotionConfig reducedMotion="always">
        <MemoryRouter>
          <PipelineTracker data={fx.pipeline} loading={false} />
        </MemoryRouter>
      </MotionConfig>,
    );
  }

  it('shows each stage’s conversion from the stage before, except the first', () => {
    renderTracker();
    const farmers = screen.getByRole('link', { name: /Farmers registered/ });
    const fields = screen.getByRole('link', { name: /Fields mapped/ });
    expect(farmers).not.toHaveTextContent('of the stage before');
    expect(fields).toHaveTextContent('80% of the stage before');
    expect(screen.getByRole('link', { name: /Fieldbooks/ })).toHaveTextContent('50% of the stage before');
  });

  it('draws the progress bar as a share of the first stage', () => {
    renderTracker();
    expect(screen.getByRole('img', { name: '40% of the first stage' })).toBeInTheDocument();
  });

  it('links every stage to its module with the filters that made the number', () => {
    renderTracker();
    expect(screen.getByRole('link', { name: /Deliveries delivered/ })).toHaveAttribute(
      'href',
      '/deliveries?tab=deliveries&status=delivered',
    );
    expect(screen.getAllByRole('listitem')).toHaveLength(7);
  });
});
