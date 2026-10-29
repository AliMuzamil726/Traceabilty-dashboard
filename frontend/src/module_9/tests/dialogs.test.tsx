import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';
import { renderWithProviders } from '@/test/renderWithProviders';
import { AcceptDialog } from '../components/AcceptDialog';
import { RejectDialog } from '../components/RejectDialog';
import { entry, json } from './fixtures';

let fetchSpy: MockInstance<typeof fetch>;

beforeEach(() => {
  fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = new URL(String(input), 'http://test');
    if (url.pathname.endsWith('/accept')) return json({ entry: entry({ status: 'accepted' }), warnings: [] });
    if (url.pathname.endsWith('/reject')) return json(entry({ status: 'rejected' }));
    return json({});
  });
});
afterEach(() => fetchSpy.mockRestore());

const called = (suffix: string) => fetchSpy.mock.calls.some(([u]) => String(u).endsWith(suffix));
const bodyOf = (suffix: string) =>
  JSON.parse(String(fetchSpy.mock.calls.find(([u]) => String(u).endsWith(suffix))![1]!.body)) as unknown;

describe('AcceptDialog', () => {
  it('shows the net weight and variance before confirming, and holds a flagged load for a note', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AcceptDialog entry={entry()} open onClose={() => undefined} />);
    await screen.findByRole('dialog', { name: /Weigh and accept DL-0001/ });
    const preview = screen.getByTestId('variance-preview');
    const net = screen.getByTestId('net-weight');
    expect(preview).toHaveTextContent('Enter the gross and tare weights');
    expect(net).toHaveTextContent('-');

    await user.type(screen.getByLabelText(/Gross weight/), '1000');
    await user.type(screen.getByLabelText(/Tare weight/), '20');
    expect(net).toHaveTextContent('980 kg (24.5 maunds)');
    expect(preview).toHaveTextContent('-20 kg (-2%)');
    expect(preview).toHaveTextContent('Within limits');

    await user.clear(screen.getByLabelText(/Gross weight/));
    await user.type(screen.getByLabelText(/Gross weight/), '1080');
    await user.type(screen.getByLabelText(/Moisture/), '9');
    expect(net).toHaveTextContent('1,060 kg (26.5 maunds)');
    expect(preview).toHaveTextContent('+60 kg (6%)');
    expect(preview).toHaveTextContent('Flagged');

    await user.click(screen.getByRole('button', { name: 'Accept load' }));
    expect(screen.getByText(/differs by more than 5%/)).toBeInTheDocument();
    expect(called('/entries/e1/accept')).toBe(false);

    await user.type(screen.getByLabelText(/Note/), 'Wet after rain');
    await user.click(screen.getByRole('button', { name: 'Accept load' }));
    await waitFor(() => expect(called('/entries/e1/accept')).toBe(true));
    expect(bodyOf('/entries/e1/accept')).toEqual({
      gross_weight_kg: 1080,
      tare_weight_kg: 20,
      moisture_pct: 9,
      note: 'Wet after rain',
    });
  });
});

describe('RejectDialog', () => {
  it('will not cancel a delivery without a reason', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RejectDialog entry={entry()} open onClose={() => undefined} />);
    await screen.findByRole('dialog', { name: /Reject DL-0001/ });
    await user.click(screen.getByRole('button', { name: 'Reject load' }));
    expect(screen.getByText(/Give a reason for rejecting the load/)).toBeInTheDocument();
    expect(called('/entries/e1/reject')).toBe(false);

    await user.type(screen.getByLabelText(/Reason/), 'Wrong vehicle for this load');
    await user.click(screen.getByRole('button', { name: 'Reject load' }));
    await waitFor(() => expect(called('/entries/e1/reject')).toBe(true));
    expect(bodyOf('/entries/e1/reject')).toEqual({ rejection_reason: 'Wrong vehicle for this load' });
  });
});
