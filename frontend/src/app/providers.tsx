import { QueryClientProvider } from '@tanstack/react-query';
import { MotionConfig } from 'framer-motion';
import { useState, type ReactNode } from 'react';
import { createQueryClient } from '@/core/api/queryClient';
import { EASE, DURATION } from '@/design-system/motion';

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user" transition={{ duration: DURATION.base, ease: EASE }}>
        {children}
      </MotionConfig>
    </QueryClientProvider>
  );
}
