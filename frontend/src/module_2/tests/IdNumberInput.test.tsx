import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '@/test/renderWithProviders';
import { IdNumberInput } from '../components/IdNumberInput';
import { SawieIdChip } from '../components/SawieIdChip';
import type { Crop } from '../api/types';

function Harness({ crop }: { crop: Crop }) {
  const [value, setValue] = useState('');
  return (
    <>
      <label htmlFor="id-number">ID number</label>
      <IdNumberInput id="id-number" crop={crop} value={value} onChange={setValue} />
    </>
  );
}

const field = () => screen.getByLabelText('ID number') as HTMLInputElement;

describe('IdNumberInput', () => {
  it('masks a CNIC as it is typed', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness crop="cotton" />);

    await user.type(field(), '35202');
    expect(field().value).toBe('35202');

    await user.type(field(), '1');
    expect(field().value).toBe('35202-1');

    await user.type(field(), '2345671');
    expect(field().value).toBe('35202-1234567-1');
  });

  it('reformats an unformatted paste', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness crop="cotton" />);
    await user.click(field());
    await user.paste('3520212345671');
    expect(field().value).toBe('35202-1234567-1');
  });

  it('reformats a paste that already has dashes', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness crop="cotton" />);
    await user.click(field());
    await user.paste('35202-1234567-1');
    expect(field().value).toBe('35202-1234567-1');
  });

  it('refuses to grow past a full CNIC', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness crop="cotton" />);
    await user.click(field());
    await user.paste('3520212345671');
    await user.type(field(), '999');
    expect(field().value).toBe('35202-1234567-1');
  });

  it('groups a hemp ID number instead of masking a CNIC', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness crop="hemp" />);
    await user.click(field());
    await user.paste('123456789');
    expect(field().value).toBe('123 456 789');
  });

  it('keeps the field numeric for both programmes', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness crop="hemp" />);
    await user.type(field(), 'abc123456789');
    expect(field().value).toBe('123 456 789');
  });
});

describe('SawieIdChip', () => {
  it('says a preview is only assigned on save', () => {
    renderWithProviders(<SawieIdChip sawieId={1042} preview />);
    expect(screen.getByText('1042')).toBeInTheDocument();
    expect(screen.getByText('Assigned on save')).toBeInTheDocument();
  });

  it('drops the hint once the ID is real', () => {
    renderWithProviders(<SawieIdChip sawieId={1042} />);
    expect(screen.getByText('1042')).toBeInTheDocument();
    expect(screen.queryByText('Assigned on save')).not.toBeInTheDocument();
  });

  it('shows nothing until there is an ID to show', () => {
    const { container } = renderWithProviders(<SawieIdChip sawieId={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('reports that it is still checking', () => {
    renderWithProviders(<SawieIdChip sawieId={null} loading />);
    expect(screen.getByText('Checking the ID number')).toBeInTheDocument();
  });
});
