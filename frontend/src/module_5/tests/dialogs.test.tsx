import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';
import { renderWithProviders } from '@/test/renderWithProviders';
import { DeliveryDetail } from '../components/DeliveryDetail';
import { ReceiveDialog } from '../components/ReceiveDialog';
import { ScheduleDialog } from '../components/ScheduleDialog';
import { delivery, json } from './fixtures';

let fetchSpy: MockInstance<typeof fetch>;
let current = delivery();

beforeEach(() => {
  current = delivery();
  fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://test');
    if (url.pathname.endsWith('/v1/sites')) {
      return json([{ id: 's1', code: 'BWP-G1', name: 'Bahawalpur Ginner 1', type: 'ginner', crop: 'cotton', country: 'PK', address: null, region: null, is_dummy: true, active: true }]);
    }
    if (url.pathname.endsWith('/v1/heaps')) return json([]);
    if (url.pathname.endsWith('/schedule')) return json({ created: [], skipped: [] }, 201);
    if (url.pathname.endsWith('/receive') && init?.method === 'POST') return json({ delivery: { ...current, status: 'delivered' }, warnings: [] });
    if (url.pathname.endsWith(`/deliveries/${current.id}`)) return json(current);
    return json({});
  });
});
afterEach(() => fetchSpy.mockRestore());

const posts = (suffix: string) => fetchSpy.mock.calls.filter(([u, i]) => String(u).endsWith(suffix) && i?.method === 'POST');

describe('ScheduleDialog', () => {
  const request = { request_id: 'r1', request_no: 'PR-0001', field_id: 'f1', field_code: '1001-01', farmer_id: 'fa1', sawie_id: 1001,
    farmer_name: 'Muhammad Imran', location: 'Multan', officer_name: null, crop: 'cotton' as const, season_year: 2026,
    estimated_quantity_kg: 1000, quantity_is_estimate: true, preferred_date: null, note: null, requested_at: '2026-10-22T00:00:00Z', can_schedule: true };

  it('shows every problem and sends nothing until they are fixed', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ScheduleDialog open requests={[request]} onClose={() => undefined} />);
    const dialog = await screen.findByRole('dialog', { name: 'Schedule 1 delivery' });
    await user.click(within(dialog).getByRole('button', { name: 'Schedule' }));
    expect(within(dialog).getByText('Choose where the crop goes.')).toBeInTheDocument();
    expect(within(dialog).getByText("Enter the driver's name.")).toBeInTheDocument();
    expect(within(dialog).getByText("Enter the driver's phone.")).toBeInTheDocument();
    expect(posts('/schedule')).toHaveLength(0);

    await waitFor(() => expect(within(dialog).getByLabelText(/Ginner/)).toHaveTextContent('Bahawalpur Ginner 1'));
    await user.selectOptions(within(dialog).getByLabelText(/Ginner/), 's1');
    await user.type(within(dialog).getByLabelText(/Driver name/), 'Akram Ali');
    await user.type(within(dialog).getByLabelText(/Driver phone/), '07700 900123');
    await user.type(within(dialog).getByLabelText(/Vehicle number/), 'mna-1234');
    await user.click(within(dialog).getByRole('button', { name: 'Schedule' }));
    expect(within(dialog).getByText(/Pakistani mobile number/)).toBeInTheDocument();
    await user.clear(within(dialog).getByLabelText(/Driver phone/));
    await user.type(within(dialog).getByLabelText(/Driver phone/), '0301 7654321');
    await user.click(within(dialog).getByRole('button', { name: 'Schedule' }));
    await waitFor(() => expect(posts('/schedule')).toHaveLength(1));
    const body = JSON.parse(String(posts('/schedule')[0]![1]!.body)) as Record<string, unknown>;
    expect(body).toMatchObject({ request_ids: ['r1'], site_id: 's1', vehicle_no: 'MNA-1234' });
  });
});

describe('ReceiveDialog', () => {
  it('previews the variance before confirming and needs a note when flagged', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ReceiveDialog delivery={current} open onClose={() => undefined} />);
    const preview = screen.getByTestId('variance-preview');
    expect(preview).toHaveTextContent('Enter the weighbridge weight');
    const weight = screen.getByLabelText(/Weighbridge weight/);
    await user.type(weight, '1020');
    expect(preview).toHaveTextContent('+20 kg (2%)');
    expect(preview).toHaveTextContent('Within limits');
    await user.clear(weight);
    await user.type(weight, '1040');
    expect(preview).toHaveTextContent('Check');
    await user.clear(weight);
    await user.type(weight, '1060');
    expect(preview).toHaveTextContent('Flagged');
    await user.type(screen.getByLabelText(/Moisture/), '13');
    expect(screen.getByText(/Above the 12% limit/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Confirm receipt' }));
    expect(screen.getByText(/differs by more than 5%/)).toBeInTheDocument();
    expect(posts('/receive')).toHaveLength(0);
    await user.type(screen.getByLabelText(/Note/), 'Wet after rain');
    await user.click(screen.getByRole('button', { name: 'Confirm receipt' }));
    await waitFor(() => expect(posts('/receive')).toHaveLength(1));
  });

  it('offers to assign the load to a heap', () => {
    renderWithProviders(<ReceiveDialog delivery={current} open onClose={() => undefined} />);
    expect(screen.getByText('Assign to heap')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open new heap' })).toBeInTheDocument();
  });
});

describe('DeliveryDetail actions follow the status', () => {
  it.each([
    ['scheduled', ['Edit schedule', 'Dispatch', 'Cancel']],
    ['in_transit', ['Receive at gate', 'Cancel']],
    ['delivered', []],
    ['cancelled', []],
  ] as const)('%s', async (status, labels) => {
    current = delivery({ status });
    renderWithProviders(<DeliveryDetail id="d1" isAdmin={false} />);
    const actions = await screen.findByLabelText('Actions');
    const names = within(actions).getAllByRole('button').map((b) => b.textContent?.trim());
    expect(names.filter((n) => n !== 'Download slip')).toEqual(labels);
  });

  it('shows Correct to administrators on delivered records, and the heap as pending', async () => {
    current = delivery({ status: 'delivered', weighbridge_weight_kg: 1000 });
    renderWithProviders(<DeliveryDetail id="d1" isAdmin />);
    const actions = await screen.findByLabelText('Actions');
    expect(within(actions).getByRole('button', { name: 'Correct' })).toBeInTheDocument();
    expect(screen.getByText('Pending: not in a heap yet.')).toBeInTheDocument();
  });
});
