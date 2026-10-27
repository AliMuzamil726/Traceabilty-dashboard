import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/renderWithProviders';
import type { Entry, EntryData } from '../api/types';
import { RepeatableEntries } from '../components/RepeatableEntries';
import { useDraftStore } from '../store/draftStore';
import { cotton, mockMasterLists, step } from './fixtures';

const weeding = step(cotton, 'weed_management');

function entry(i: number, data: EntryData): Entry {
  return { entry_index: i, data, completed: true, updated_at: '2026-06-01T00:00:00Z', updated_by: null };
}

let fetchSpy: ReturnType<typeof mockMasterLists>;
beforeEach(() => {
  fetchSpy = mockMasterLists();
  useDraftStore.setState({ drafts: {} });
});
afterEach(() => fetchSpy.mockRestore());

/** Plays the server: saving appends or replaces, deleting removes. */
function Harness({ onSaveSpy }: { onSaveSpy: (which: number | 'new', data: EntryData) => void }) {
  const [entries, setEntries] = useState<Entry[]>([entry(0, { weed_date: '2026-06-01', method: 'manual_weeding' })]);
  return (
    <RepeatableEntries
      bookId="b1"
      step={weeding}
      entries={entries}
      defaults={{}}
      country="PK"
      crop="cotton"
      labelOf={(_, v) => (v === 'manual_weeding' ? 'Manual weeding' : v)}
      onSave={async (which, data) => {
        onSaveSpy(which, data);
        setEntries((prev) =>
          which === 'new'
            ? [...prev, entry(Math.max(-1, ...prev.map((e) => e.entry_index)) + 1, data)]
            : prev.map((e) => (e.entry_index === which ? entry(which, data) : e)),
        );
        return { ok: true, fieldErrors: {}, warnings: {} };
      }}
      onDelete={(i) => setEntries((prev) => prev.filter((e) => e.entry_index !== i))}
    />
  );
}

describe('RepeatableEntries', () => {
  it('shows each entry as a summary line with the step totals', () => {
    renderWithProviders(<Harness onSaveSpy={vi.fn()} />);
    expect(screen.getByRole('button', { name: /Entry 1/ })).toHaveTextContent('Manual weeding');
    expect(screen.getByTestId('step-totals')).toHaveTextContent('1');
  });

  it('adds a new entry', async () => {
    const user = userEvent.setup();
    const spy = vi.fn();
    renderWithProviders(<Harness onSaveSpy={spy} />);
    await user.click(screen.getByRole('button', { name: 'Add entry' }));
    const method = within(document.querySelector('[data-field="method"]') as HTMLElement).getByRole('combobox');
    await waitFor(() => expect(within(method).getAllByRole('option').length).toBeGreaterThan(1));
    await user.selectOptions(method, 'manual_weeding');
    const date = document.querySelector('[data-field="weed_date"] input') as HTMLInputElement;
    await user.type(date, '2026-06-10');
    await user.click(screen.getByRole('button', { name: 'Save entry' }));
    expect(spy).toHaveBeenCalledWith('new', expect.objectContaining({ method: 'manual_weeding' }));
    expect(screen.getByRole('button', { name: /Entry 2/ })).toBeInTheDocument();
  });

  it('duplicates an entry into a new unsaved one', async () => {
    const user = userEvent.setup();
    const spy = vi.fn();
    renderWithProviders(<Harness onSaveSpy={spy} />);
    await user.click(screen.getByRole('button', { name: /Entry 1/ }));
    await user.click(screen.getByRole('button', { name: 'Duplicate' }));
    expect(screen.getByRole('button', { name: /Entry 2/ })).toHaveTextContent('Not saved');
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Save entry' })).toHaveLength(1));
    await user.click(screen.getByRole('button', { name: 'Save entry' }));
    expect(spy).toHaveBeenCalledWith('new', { weed_date: '2026-06-01', method: 'manual_weeding' });
  });

  it('deletes only after confirmation', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness onSaveSpy={vi.fn()} />);
    await user.click(screen.getByRole('button', { name: /Entry 1/ }));
    await user.click(screen.getByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('alertdialog');
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.getByRole('button', { name: /Entry 1/ })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Delete' }));
    await user.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Delete entry' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: /Entry 1/ })).toBeNull());
    expect(screen.getByText(/No weed management recorded yet/)).toBeInTheDocument();
  });
});
