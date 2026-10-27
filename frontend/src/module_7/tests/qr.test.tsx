import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';
import { renderWithProviders } from '@/test/renderWithProviders';
import { BaseUrlWarning } from '../components/BaseUrlWarning';
import { FindCodeBox } from '../components/FindCodeBox';
import { classifyCode, isLocalBaseUrl } from '../lib/codes';
import PublicTracePage from '../pages/PublicTracePage';
import { INVALID, json, publicTrace } from './fixtures';

const TOKEN = 'ABCDEFGHJKMN';
let fetchSpy: MockInstance<typeof fetch>;
let respond: (url: URL) => Response;

beforeEach(() => {
  respond = () => json({});
  fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => respond(new URL(String(input), 'http://test')));
});
afterEach(() => fetchSpy.mockRestore());

function renderPublic(token = TOKEN) {
  return renderWithProviders(<Routes><Route path="/trace/:token" element={<PublicTracePage />} /></Routes>, { route: `/trace/${token}` });
}

describe('PublicTracePage', () => {
  it('shows a valid bale with its journey and checks, and no personal data', async () => {
    respond = () => json(publicTrace());
    renderPublic();
    expect(await screen.findByRole('heading', { name: 'Cotton lint bale' })).toBeInTheDocument();
    expect(screen.getByText('BWP-G1-H01-001')).toBeInTheDocument();
    expect(screen.getByText('170 kg')).toBeInTheDocument();
    expect(screen.getByText('Multan')).toBeInTheDocument();
    expect(screen.getByText('All checks passed')).toBeInTheDocument();
    expect(within(screen.getByRole('list', { name: 'Chain of custody' })).getAllByRole('listitem')).toHaveLength(2);
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument(); // outside the app shell
    const call = new URL(String(fetchSpy.mock.calls[0]?.[0]), 'http://test');
    expect(call.pathname).toBe(`/api/v1/qr/public/${TOKEN}`);
  });

  it('says a revoked or unknown code is not valid', async () => {
    respond = () => json(INVALID, 404);
    renderPublic();
    expect(await screen.findByRole('heading', { name: 'This code is not valid' })).toBeInTheDocument();
    expect(screen.queryByText('Cotton lint bale')).not.toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledTimes(1); // a 404 is final, never retried
  });

  it('shows a failed check plainly', async () => {
    respond = () => json(publicTrace({
      checks: [
        { key: 'fieldbooks_submitted', label: 'All fieldbooks submitted', passed: false, detail: '2 of 3 submitted.' },
        { key: 'heap_closed', label: 'Heap closed', passed: true, detail: 'Closed.' },
      ],
    }));
    renderPublic();
    expect(await screen.findByText('Some checks have not passed yet')).toBeInTheDocument();
    const failed = screen.getByText('All fieldbooks submitted').closest('li');
    expect(failed).toHaveAttribute('data-passed', 'false');
    expect(within(failed as HTMLElement).getByText(': not passed')).toBeInTheDocument();
    expect(screen.getByText('1 of 2 checks passed')).toBeInTheDocument();
  });
});

describe('BaseUrlWarning', () => {
  it('warns for localhost and 127.0.0.1, and not for a network address', () => {
    const { rerender } = renderWithProviders(<BaseUrlWarning baseUrl="http://localhost:5173" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Phones cannot open these codes yet');
    rerender(<BaseUrlWarning baseUrl="http://127.0.0.1:5173" />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    rerender(<BaseUrlWarning baseUrl="http://192.168.1.20:5173" />);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(isLocalBaseUrl('https://trace.example.org')).toBe(false);
  });
});

describe('FindCodeBox', () => {
  it('classifies codes, serials and links', () => {
    expect(classifyCode(` ${TOKEN.toLowerCase()} `)).toEqual({ kind: 'token', token: TOKEN, text: TOKEN.toLowerCase() });
    expect(classifyCode('bwp-g1-h01-001')).toEqual({ kind: 'serial', text: 'BWP-G1-H01-001' });
    expect(classifyCode(`http://192.168.1.20:5173/trace/${TOKEN}?src=label`)).toMatchObject({ kind: 'url', token: TOKEN });
    expect(classifyCode('  ').kind).toBe('empty');
  });

  it.each([
    ['a code', TOKEN, TOKEN],
    ['a bale serial', 'BWP-G1-H01-001', 'BWP-G1-H01-001'],
    ['a trace link', `http://192.168.1.20:5173/trace/${TOKEN}`, TOKEN],
  ])('resolves %s', async (_name, typed, sent) => {
    const resolved = { kind: 'bale', heap_id: 'BWP-G1-H01', bale_serial: 'BWP-G1-H01-001', token: TOKEN, token_status: 'active' };
    respond = () => json(resolved);
    const onFound = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<FindCodeBox onFound={onFound} />);
    await user.type(screen.getByLabelText('Find a code'), typed);
    await user.click(screen.getByRole('button', { name: 'Find' }));
    await waitFor(() => expect(onFound).toHaveBeenCalledWith(resolved));
    const call = new URL(String(fetchSpy.mock.calls.at(-1)?.[0]), 'http://test');
    expect(call.pathname).toBe('/api/v1/qr/resolve');
    expect(call.searchParams.get('q')).toBe(sent);
  });

  it('shows the server message when nothing matches', async () => {
    respond = () => json({ error: { code: 'qr_not_found', message: 'No bale, lot or code matches that.', details: null } }, 404);
    const user = userEvent.setup();
    renderWithProviders(<FindCodeBox onFound={vi.fn()} />);
    await user.type(screen.getByLabelText('Find a code'), 'NOPE');
    await user.click(screen.getByRole('button', { name: 'Find' }));
    expect(await screen.findByText('No bale, lot or code matches that.')).toBeInTheDocument();
  });

  it('explains when the browser cannot scan with the camera', async () => {
    const user = userEvent.setup();
    renderWithProviders(<FindCodeBox onFound={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: 'Scan' }));
    expect(await screen.findByText(/This browser cannot scan codes with the camera/)).toBeInTheDocument();
  });
});
