import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { cn } from '@/core/utils/cn';
import { pageVariants } from '@/design-system/motion';

export interface PageContainerProps {
  children: ReactNode;
  className?: string;
  /** Full-bleed pages (maps) skip the max width. */
  wide?: boolean;
}

/** Page frame with the standard page transition (fade + 8px rise). */
export function PageContainer({ children, className, wide }: PageContainerProps) {
  return (
    <motion.div
      variants={pageVariants}
      initial="initial"
      animate="animate"
      className={cn('mx-auto w-full px-4 py-6 sm:px-6 lg:px-8 lg:py-8', !wide && 'max-w-[1440px]', className)}
    >
      {children}
    </motion.div>
  );
}
