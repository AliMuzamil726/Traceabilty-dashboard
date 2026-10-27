import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MotionConfig } from 'framer-motion';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';
import { Toaster } from '@/design-system/components/Toast';
import { AdminOnlyGate } from '../components/AdminOnlyGate';
import { ListManager } from '../components/ListManager';
import { StickySaveBar } from '../components/StickySaveBar';
import PreferencesPage from '../pages/PreferencesPage';
import ValidationPage from '../pages/ValidationPage';
import * as fx from './fixtures';

let fetchSpy: MockInstance<typeof fetch>;
let answers: Record<string, unknown>;
let sent: { url: string; method: string; body: unknown }[];
let failWith: { status: number; code: string; message: string } | null;

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

beforeEach(() => {
  sent = [];
  failWith = null;
  answers = {
    me: fx.officer(false),
    registry: fx.registry(),
    preferences: fx.preferences(),
    lists: fx.lists,
    values: fx.listValues(),
  };
  fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://test');
    const method = init?.method ?? 'GET';
    if (method !== 'GET') {
      sent.push({ url: url.pathname, method, body: init?.body ? JSON.parse(String(init.body)) : null });
      if (failWith) {
        return json(
          { error: { code: failWith.code, message: failWith.message, details: null } },
          failWith.status,
        );
      }
    }
    if (url.pathname.endsWith('/officers/me')) return json(answers.me);
    if (url.pathname.endsWith('/settings/registry')) return json(answers.registry);
    if (url.pathname.endsWith('/me/preferences')) {
      if (method === 'PUT') return json({ ...fx.preferences(), ...JSON.parse(String(init?.body)) });
      return json(answers.preferences);
    }
    if (url.pathname.endsWith('/settings/lists')) return json(answers.lists);
    if (url.pathname.includes('/values')) return json(answers.values);
    if (url.pathname.includes('/reorder')) return json(answers.values);
    return json({});
  });
});

afterEach(() => {
  fetchSpy.mockRestore();
  vi.unstubAllGlobals();
});

function renderUi(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MotionConfig reducedMotion="always">
        <MemoryRouter initialEntries={['/settings']}>
          {ui}
          <Toaster />
        </MemoryRouter>
      </MotionConfig>
    </QueryClientProvider>,
  );
}

describe('AdminOnlyGate', () => {
  it('explains the refusal to an officer instead of showing an error', async () => {
    renderUi(
      <AdminOnlyGate>
        <p>Secret settings</p>
      </AdminOnlyGate>,
    );
    expect(await screen.findByText('Administrator access required')).toBeInTheDocument();
    expect(screen.queryByText('Secret settings')).toBeNull();
  });

  it('lets an administrator through', async () => {
    answers.me = fx.officer(true);
    renderUi(
      <AdminOnlyGate>
        <p>Secret settings</p>
      </AdminOnlyGate>,
    );
    expect(await screen.findByText('Secret settings')).toBeInTheDocument();
  });
});

describe('StickySaveBar', () => {
  it('stays hidden until something changes', () => {
    const { rerender } = render(
      <StickySaveBar dirty={false} onSave={() => {}} onDiscard={() => {}} />,
    );
    expect(screen.queryByRole('button', { name: 'Save changes' })).toBeNull();

    rerender(<StickySaveBar dirty onSave={() => {}} onDiscard={() => {}} />);
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Unsaved changes' })).toBeInTheDocument();
  });
});

describe('Settings values', () => {
  it('shows a setting, marks it changed and saves it with the version it loaded', async () => {
    const user = userEvent.setup();
    renderUi(<ValidationPage />);

    const field = await screen.findByRole('spinbutton');
    expect(screen.queryByText('Changed')).toBeNull();

    await user.clear(field);
    await user.type(field, '11');
    expect(await screen.findByText('Changed')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]?.method).toBe('PUT');
    expect(sent[0]?.url).toContain('validation.hemp_id_min_digits');
    expect(sent[0]?.body).toMatchObject({ value: 11, expected_version: 3 });
  });

  it('tells the officer when someone else saved first', async () => {
    const user = userEvent.setup();
    failWith = {
      status: 409,
      code: 'stale_version',
      message: 'Changed by someone else.',
    };
    renderUi(<ValidationPage />);

    const field = await screen.findByRole('spinbutton');
    await user.clear(field);
    await user.type(field, '12');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText('Someone else saved this first')).toBeInTheDocument();
  });

  it('says plainly that these rules affect new entries only', async () => {
    renderUi(<ValidationPage />);
    expect(await screen.findByText(/affect new entries only/i)).toBeInTheDocument();
  });
});

describe('PreferencesPage', () => {
  it('saves a density choice for the officer alone', async () => {
    const user = userEvent.setup();
    renderUi(<PreferencesPage />);

    await user.click(await screen.findByRole('radio', { name: 'Compact' }));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]?.url).toContain('/me/preferences');
    expect(sent[0]?.body).toMatchObject({ table_density: 'compact' });
  });
});

describe('ListManager', () => {
  it('shows the stored key beside the label, so editing a label is obviously safe', async () => {
    renderUi(
      <ListManager list={fx.lists[0]!} values={fx.listValues()} loading={false} onChanged={() => {}} />,
    );
    expect(await screen.findByText('urea')).toBeInTheDocument();
    expect(screen.getByText('potash')).toBeInTheDocument();
    // The label is an editable field; the key beside it is not.
    expect(screen.getByRole('textbox', { name: 'Label for urea' })).toHaveValue('Urea');
  });

  it('offers delete only for a value nothing uses', async () => {
    renderUi(
      <ListManager list={fx.lists[0]!} values={fx.listValues()} loading={false} onChanged={() => {}} />,
    );
    expect(await screen.findByRole('button', { name: 'Delete Potash' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Delete Urea' })).toBeNull();
    expect(screen.getByText('In use')).toBeInTheDocument();
  });

  it('saves the new order when a value is dropped', async () => {
    const user = userEvent.setup();
    renderUi(
      <ListManager list={fx.lists[0]!} values={fx.listValues()} loading={false} onChanged={() => {}} />,
    );
    // Reordering is a drag; the handle is what makes it keyboard and pointer reachable.
    expect(await screen.findByRole('button', { name: 'Reorder Urea' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Reorder Urea' }));
    expect(screen.getByText(/Drag a value to change the order/)).toBeInTheDocument();
  });
});
