import type { Transition, Variants } from 'framer-motion';

/** Restrained motion tokens: 120 / 200 / 320 ms on one easing curve. */
export const DURATION = { fast: 0.12, base: 0.2, slow: 0.32 } as const;
export const EASE: [number, number, number, number] = [0.2, 0.8, 0.2, 1];

export const transition = (duration: keyof typeof DURATION = 'base'): Transition => ({
  duration: DURATION[duration],
  ease: EASE,
});

/** Page transition: fade + 8px rise. */
export const pageVariants: Variants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: transition('slow') },
  exit: { opacity: 0, transition: transition('fast') },
};

export const STAGGER_STEP = 0.03;
export const STAGGER_MAX_ITEMS = 8;

/** Stagger delay for list item `index`: 30ms steps, capped after 8 items. */
export function staggerDelay(index: number): number {
  return Math.min(index, STAGGER_MAX_ITEMS - 1) * STAGGER_STEP;
}

export const listItemVariants: Variants = {
  initial: { opacity: 0, y: 6 },
  animate: (index: number) => ({
    opacity: 1,
    y: 0,
    transition: { ...transition('base'), delay: staggerDelay(index) },
  }),
};

export const overlayVariants: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: transition('base') },
  exit: { opacity: 0, transition: transition('fast') },
};

export const dialogVariants: Variants = {
  initial: { opacity: 0, y: 8, scale: 0.98 },
  animate: { opacity: 1, y: 0, scale: 1, transition: transition('base') },
  exit: { opacity: 0, y: 4, scale: 0.99, transition: transition('fast') },
};

