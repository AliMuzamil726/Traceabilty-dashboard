import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'framer-motion';
import { DURATION } from '@/design-system/motion';

/**
 * Count a KPI up to its value once, when it arrives.
 *
 * Restrained on purpose: it runs for one 320 ms step, only when the number changes,
 * and not at all under reduced motion, where the value simply appears. A figure that
 * keeps animating is harder to read, not easier.
 */
export function useCountUp(target: number, durationSeconds = DURATION.slow): number {
  const reduced = useReducedMotion();
  const [value, setValue] = useState(reduced ? target : 0);
  const from = useRef(0);

  useEffect(() => {
    if (reduced) {
      setValue(target);
      return;
    }
    const start = from.current;
    if (start === target) {
      setValue(target);
      return;
    }
    const began = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const progress = Math.min(1, (now - began) / (durationSeconds * 1000));
      // Ease out, so it settles rather than stopping dead.
      const eased = 1 - (1 - progress) ** 3;
      setValue(Math.round(start + (target - start) * eased));
      if (progress < 1) frame = requestAnimationFrame(step);
      else from.current = target;
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, durationSeconds, reduced]);

  return value;
}
