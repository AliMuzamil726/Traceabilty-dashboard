import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { MotionConfig } from 'framer-motion';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';

export function renderWithProviders(ui: ReactElement, { route = '/' }: { route?: string } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MotionConfig reducedMotion="always">
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </MotionConfig>
    </QueryClientProvider>,
  );
}
