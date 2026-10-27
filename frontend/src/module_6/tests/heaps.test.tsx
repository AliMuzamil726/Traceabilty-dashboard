import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';
import { renderWithProviders } from '@/test/renderWithProviders';
import { HeapPicker } from '..';
import { CloseHeapDialog } from '../components/CloseHeapDialog';
import { HeapHeader } from '../components/HeapHeader';
import { RecordBalesDialog } from '../components/RecordBalesDialog';
import { closeState, validateBaleCount } from '../lib/rules';
import { words } from '../lib/wording';
import { heap, json } from './fixtures';

let fetchSpy: MockInstance<typeof fetch>;
beforeEach(() => {
  fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://test');
    if (url.pathname.endsWith('/v1/heaps') && init?.method === 'POST') {
      return json({ heap: heap({ id: 'h3', heap_id: 'BWP-G1-H03' }), warnings: ['BWP-G1-H01 is already open.'] }, 201);
    }
    if (url.pathname.endsWith('/v1/heaps')) {
      return json([
        { id: 'h1', heap_id: 'BWP-G1-H01', site_id: 's1', crop: 'cotton', status: 'open', opened_at: '', closed_at: null, deliveries: 3, input_kg: '1.00', bales_made: 0 },
        { id: 'h2', heap_id: 'BWP-G1-H02', site_id: 's1', crop: 'cotton', status: 'open', opened_at: '', closed_at: null, deliveries: 1, input_kg: '1.00', bales_made: 0 },
      ]);
    }
    return json({});
  });
});
afterEach(() => fetchSpy.mockRestore());

describe('HeapPicker', () => {
  it('lists the open heaps at the site and opens a new one', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(<HeapPicker siteId="s1" crop="cotton" value={null} onChange={onChange} />);
    const select = screen.getByLabelText('Open heap');
    await waitFor(() => expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Choose an open heap', 'BWP-G1-H01 (3 deliveries)', 'BWP-G1-H02 (1 delivery)']));
    const listCall = fetchSpy.mock.calls.map(([u]) => new URL(String(u), 'http://test')).find((u) => u.pathname.endsWith('/v1/heaps'));
    expect(listCall?.searchParams.get('status')).toBe('open');
    expect(listCall?.searchParams.get('site_id')).toBe('s1');
    await user.selectOptions(select, 'h2');
    expect(onChange).toHaveBeenLastCalledWith('h2');
    await user.click(screen.getByRole('button', { name: 'Open new heap' }));
    await waitFor(() => expect(onChange).toHaveBeenLastCalledWith('h3'));
  });

  it('says batch for hemp', () => {
    renderWithProviders(<HeapPicker siteId="s2" crop="hemp" value={null} onChange={() => undefined} />);
    expect(screen.getByLabelText('Open batch')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open new batch' })).toBeInTheDocument();
  });
});

describe('Record bales', () => {
  it('validates the count against the remaining maximum', () => {
    expect(validateBaleCount(5, 34)).toBeNull();
    expect(validateBaleCount(34, 34)).toBeNull();
    expect(validateBaleCount(35, 34)).toBe('At most 34 more bales fit the expected output.');
    expect(validateBaleCount(2, 1)).toBe('At most 1 more bale fits the expected output.');
    expect(validateBaleCount(0, 34)).toBe('Record at least one bale.');
    expect(validateBaleCount(1.5, 34)).toBe('Enter a whole number of bales.');
    expect(validateBaleCount(null, 34)).toBe('Enter how many bales were made.');
    expect(validateBaleCount(1, 0)).toBe('No more bales fit the expected output.');
  });

  it('refuses too many bales before calling the server', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RecordBalesDialog heap={heap({ totals: { ...heap().totals, can_add_bales: 2 } })} open onClose={() => undefined} />);
    const input = screen.getByLabelText(/Number of bales/);
    await user.clear(input);
    await user.type(input, '3');
    await user.click(screen.getByRole('button', { name: 'Record' }));
    expect(screen.getByText('At most 2 more bales fit the expected output.')).toBeInTheDocument();
    expect(fetchSpy.mock.calls.some(([u, i]) => String(u).endsWith('/bales') && i?.method === 'POST')).toBe(false);
  });
});

describe('Close button states', () => {
  const t = heap().totals;
  it.each([
    ['nothing to close yet', heap({ deliveries: [] }), 'none'],
    ['remainder, officer', heap(), 'none'],
    ['remainder, administrator', heap({ permissions: { ...heap().permissions, can_close_with_remainder: true } }), 'remainder'],
    ['no remainder', heap({ totals: { ...t, can_close: true }, permissions: { ...heap().permissions, can_close: true } }), 'close'],
    ['closed', heap({ status: 'closed' }), 'none'],
  ] as const)('%s', (_, h, mode) => {
    expect(closeState(h).mode).toBe(mode);
  });

  it('shows a disabled close to an officer while output remains', () => {
    renderWithProviders(<CloseHeapDialog heap={heap()} />);
    expect(screen.getByRole('button', { name: 'Close heap' })).toHaveAttribute('aria-disabled', 'true');
  });

  it('offers Close with remainder to an administrator, with a required reason', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CloseHeapDialog heap={heap({ permissions: { ...heap().permissions, can_close_with_remainder: true } })} />);
    await user.click(screen.getByRole('button', { name: 'Close with remainder' }));
    const dialog = await screen.findByRole('alertdialog');
    expect(dialog).toHaveTextContent('17,000 kg of input');
    await user.click(within(dialog).getByRole('button', { name: 'Close heap' }));
    expect(within(dialog).getByText('Closing with a remainder needs a reason.')).toBeInTheDocument();
  });

  it('enables a plain close when nothing remains', () => {
    const h = heap({ totals: { ...t, can_close: true }, permissions: { ...heap().permissions, can_close: true } });
    renderWithProviders(<CloseHeapDialog heap={h} />);
    expect(screen.getByRole('button', { name: 'Close heap' })).not.toHaveAttribute('aria-disabled');
  });
});

describe('wording', () => {
  it('switches between heap and batch', () => {
    expect(words('cotton')).toMatchObject({ lot: 'Heap', site: 'Ginner' });
    expect(words('hemp')).toMatchObject({ lot: 'Batch', site: 'Processor' });
    renderWithProviders(<HeapHeader heap={heap()} />);
    expect(screen.getByText('Heap')).toBeInTheDocument();
    expect(screen.getByText(/Ginner: Bahawalpur Ginner 1/)).toBeInTheDocument();
  });

  it('uses Batch and Processor for hemp', () => {
    renderWithProviders(<HeapHeader heap={heap({ crop: 'hemp', heap_id: 'UK-P1-BT01', site: { id: 's', code: 'UK-P1', name: 'Norfolk Processor', type: 'processor', address: null } })} />);
    expect(screen.getByText('Batch')).toBeInTheDocument();
    expect(screen.getByText(/Processor: Norfolk Processor/)).toBeInTheDocument();
    renderWithProviders(<CloseHeapDialog heap={heap({ crop: 'hemp', totals: { ...heap().totals, can_close: true }, permissions: { ...heap().permissions, can_close: true } })} />);
    expect(screen.getByRole('button', { name: 'Close batch' })).toBeInTheDocument();
  });
});
