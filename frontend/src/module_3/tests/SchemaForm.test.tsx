import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { renderWithProviders } from '@/test/renderWithProviders';
import type { EntryData, FormDefinition, StepDef } from '../api/types';
import { SchemaForm } from '../components/SchemaForm';
import { isVisible } from '../lib/schemaLogic';
import { cotton, hemp, mockMasterLists, step } from './fixtures';

let fetchSpy: ReturnType<typeof mockMasterLists>;
beforeEach(() => {
  fetchSpy = mockMasterLists();
});
afterEach(() => fetchSpy.mockRestore());

function Harness({ def, s, initial = {} }: { def: FormDefinition; s: StepDef; initial?: EntryData }) {
  const [values, setValues] = useState<EntryData>(initial);
  return (
    <>
      <SchemaForm step={s} values={values} onChange={setValues} country={def.country} crop={def.crop} photos={<p>Photo slot</p>} />
      <output data-testid="values">{JSON.stringify(values)}</output>
    </>
  );
}

/** Values that make every conditional field of a step visible, where one value can. */
function revealAll(s: StepDef): EntryData {
  const values: EntryData = {};
  for (const f of s.fields) {
    const cond = f.visible_if;
    if (cond?.in?.[0] && values[cond.field] === undefined) values[cond.field] = cond.in[0];
  }
  return values;
}

describe.each([
  ['cotton', cotton],
  ['hemp', hemp],
])('%s schema', (_, def) => {
  it.each(def.steps.map((s) => [s.key, s] as const))('renders every visible field of %s', async (_key, s) => {
    const values = revealAll(s);
    renderWithProviders(<Harness def={def} s={s} initial={values} />);
    for (const f of s.fields.filter((field) => isVisible(field, values))) {
      const node = document.querySelector(`[data-field="${f.key}"]`);
      expect(node, `${s.key}.${f.key}`).not.toBeNull();
      expect(node).toHaveTextContent(f.label);
    }
    // List-backed fields fill their options from the master lists, never from code.
    const listField = s.fields.find((f) => f.type === 'select' && isVisible(f, values));
    if (listField) {
      const select = within(document.querySelector(`[data-field="${listField.key}"]`) as HTMLElement).getByRole('combobox');
      await waitFor(() => expect(within(select).getAllByRole('option').length).toBeGreaterThan(1));
    }
  });
});

describe('field types', () => {
  it('covers every type the renderer supports across both schemas', () => {
    const types = new Set([...cotton.steps, ...hemp.steps].flatMap((s) => s.fields.map((f) => f.type)));
    expect([...types].sort()).toEqual(
      ['date', 'dates', 'multiselect', 'number', 'paired_number', 'photos', 'select', 'text', 'yesno'].sort(),
    );
  });

  it('draws the photo slot in place of the photos field', () => {
    renderWithProviders(<Harness def={cotton} s={step(cotton, 'field_info')} />);
    expect(screen.getByText('Photo slot')).toBeInTheDocument();
  });

  it('adds and removes dates in a date list and counts them', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness def={hemp} s={step(hemp, 'retting')} />);
    await user.click(screen.getByRole('button', { name: 'Add date' }));
    await user.click(screen.getByRole('button', { name: 'Add date' }));
    expect(screen.getAllByLabelText(/^Turning dates \d$/)).toHaveLength(2);
    await user.click(screen.getByRole('button', { name: 'Remove turning dates 1' }));
    expect(screen.getAllByLabelText(/^Turning dates \d$/)).toHaveLength(1);
  });

  it('fills computed fields as the officer types', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness def={hemp} s={step(hemp, 'baling')} />);
    await user.type(within(document.querySelector('[data-field="number_of_bales"]') as HTMLElement).getByRole('spinbutton'), '20');
    await user.type(within(document.querySelector('[data-field="avg_bale_weight"]') as HTMLElement).getByRole('spinbutton'), '450');
    expect(JSON.parse(screen.getByTestId('values').textContent ?? '{}').total_straw_weight).toBe(9000);
    expect(within(document.querySelector('[data-field="total_straw_weight"]') as HTMLElement).getByRole('spinbutton')).toHaveAttribute('readonly');
  });

  it('offers the typical fertiliser analysis once a product is chosen', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness def={cotton} s={step(cotton, 'nutrient_management')} />);
    const product = within(document.querySelector('[data-field="product"]') as HTMLElement).getByRole('combobox');
    await waitFor(() => expect(within(product).getAllByRole('option').length).toBeGreaterThan(1));
    await user.selectOptions(product, 'urea');
    await user.click(screen.getByRole('button', { name: /Use typical value: 46/ }));
    expect(JSON.parse(screen.getByTestId('values').textContent ?? '{}').n_content).toBe(46);
  });
});

describe('conditional fields', () => {
  it('shows diesel only for a diesel tubewell', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness def={cotton} s={step(cotton, 'irrigation')} />);
    expect(document.querySelector('[data-field="diesel_used"]')).toBeNull();
    const source = within(document.querySelector('[data-field="source"]') as HTMLElement).getByRole('combobox');
    await waitFor(() => expect(within(source).getAllByRole('option').length).toBeGreaterThan(1));
    await user.selectOptions(source, 'tubewell_diesel');
    expect(document.querySelector('[data-field="diesel_used"]')).not.toBeNull();
    expect(document.querySelector('[data-field="pumping_head"]')).not.toBeNull();
    await user.selectOptions(source, 'canal');
    await waitFor(() => expect(document.querySelector('[data-field="diesel_used"]')).toBeNull());
  });

  it('hides diesel per pass for bullock-drawn work (not_in)', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness def={cotton} s={step(cotton, 'land_preparation')} />);
    expect(document.querySelector('[data-field="diesel_per_pass"]')).not.toBeNull();
    const machinery = within(document.querySelector('[data-field="machinery_type"]') as HTMLElement).getByRole('combobox');
    await waitFor(() => expect(within(machinery).getAllByRole('option').length).toBeGreaterThan(1));
    await user.selectOptions(machinery, 'bullock_drawn');
    await waitFor(() => expect(document.querySelector('[data-field="diesel_per_pass"]')).toBeNull());
  });

  it('asks for the training name only when training was attended', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness def={cotton} s={step(cotton, 'labour_social')} />);
    expect(screen.queryByText('Training name')).toBeNull();
    const group = screen.getByRole('radiogroup', { name: 'Training attended' });
    await waitFor(() => expect(within(group).getAllByRole('radio')).toHaveLength(2));
    await user.click(within(group).getByRole('radio', { name: 'Yes' }));
    expect(screen.getByText('Training name')).toBeInTheDocument();
  });
});
