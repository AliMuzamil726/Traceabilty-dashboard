import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useUiStore } from '@/core/store/uiStore';
import { renderWithProviders } from '@/test/renderWithProviders';
import { SidebarContent } from './Sidebar';

const ADMIN = { id: 'a1', code: 'ADMIN-01', full_name: 'Admin', role: 'admin', country: 'PK', field_office_id: null, field_office_name: null, is_admin: true, sees_all: true };

describe('Sidebar', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      async () => new Response(JSON.stringify(ADMIN), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
  });
  afterEach(() => vi.restoreAllMocks());

  it('renders all eight modules in order', async () => {
    renderWithProviders(<SidebarContent />);
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    await within(nav).findByText('Settings');
    // The eight modules, then My profile and Sign out (the collapse toggle only on the rail).
    const items = within(nav).getAllByRole('listitem');
    expect(items).toHaveLength(10);
    expect(items.map((li) => li.textContent)).toEqual([
      expect.stringContaining('Home'),
      expect.stringContaining('Register Farmer'),
      expect.stringContaining('Fieldbook'),
      expect.stringContaining('Harvest Radar'),
      expect.stringContaining('Deliveries'),
      expect.stringContaining('Heap'),
      expect.stringContaining('QR Tracing'),
      expect.stringContaining('Settings'),
      expect.stringContaining('My profile'),
      expect.stringContaining('Sign out'),
    ]);
  });

  it('puts Settings below the rule, linked and enabled', async () => {
    renderWithProviders(<SidebarContent />);
    const settings = await screen.findByRole('link', { name: /Settings/ });
    expect(settings).toHaveAttribute('href', '/settings');
    expect(settings).not.toHaveAttribute('aria-disabled');
    expect(settings).not.toHaveTextContent('Coming later');
  });

  it('links every built route and marks build status', async () => {
    renderWithProviders(<SidebarContent />, { route: '/register' });
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    await within(nav).findByText('Settings');
    const links = within(nav)
      .getAllByRole('link')
      .filter((a) => a.hasAttribute('href'));
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/', '/register', '/fieldbook', '/radar', '/deliveries', '/heaps', '/qr', '/settings', '/profile']);
    expect(screen.getByRole('link', { name: /Register Farmer/ })).toHaveAttribute('aria-current', 'page');
    // Modules 1 to 7 are all built, so no In build or Planned pill is left.
    expect(screen.getByRole('link', { name: /Register Farmer/ })).not.toHaveTextContent('In build');
    expect(screen.getByRole('link', { name: /Fieldbook/ })).not.toHaveTextContent('In build');
    expect(screen.getByRole('link', { name: /Harvest Radar/ })).not.toHaveTextContent('In build');
    expect(screen.getByRole('link', { name: /Deliveries/ })).not.toHaveTextContent('In build');
    expect(screen.getByRole('link', { name: /Heap/ })).not.toHaveTextContent('In build');
    expect(screen.getByRole('link', { name: /QR Tracing/ })).not.toHaveTextContent('In build');
    expect(screen.getByRole('link', { name: /Home/ })).not.toHaveTextContent('In build');
    expect(screen.queryByText('Planned')).toBeNull();
  });

  it('collapses to an icon rail with accessible names', async () => {
    useUiStore.setState({ sidebarCollapsed: false });
    const user = userEvent.setup();
    const first = renderWithProviders(<SidebarContent showCollapseToggle collapsed={false} />);
    await user.click(screen.getByRole('button', { name: 'Collapse sidebar' }));
    expect(useUiStore.getState().sidebarCollapsed).toBe(true);
    first.unmount();
    renderWithProviders(<SidebarContent showCollapseToggle collapsed />);
    expect(screen.queryByText('Fibre-crop traceability')).toBeNull();
    expect(await screen.findByRole('link', { name: 'Fieldbook' })).toHaveAttribute('href', '/fieldbook');
    expect(screen.getByRole('button', { name: 'Expand sidebar' })).toBeInTheDocument();
  });
});
