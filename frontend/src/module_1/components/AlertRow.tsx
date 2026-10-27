import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { Link as RouterLink } from 'react-router-dom';
import { cn } from '@/core/utils/cn';
import { formatNumber } from '@/core/utils/format';
import { Badge } from '@/design-system/components/Badge';
import { listItemVariants } from '@/design-system/motion';
import type { Alert } from '../api/types';
import { toHref } from '../lib/links';

export interface AlertRowProps {
  alert: Alert;
  index: number;
}

/**
 * One rule that found something: the count, how serious it is, the first few records
 * by name and a link to the filtered view that shows them all.
 *
 * Severity decides the colour, and only a critical rule uses the error red: a backlog
 * is wheat, a loss of traceability or an expired licence is red.
 */
export function AlertRow({ alert, index }: AlertRowProps) {
  const critical = alert.severity === 'critical';
  return (
    <motion.li
      custom={index}
      variants={listItemVariants}
      initial="initial"
      animate="animate"
      className={cn(
        'rounded-control border bg-surface p-3',
        critical ? 'border-danger/30' : 'border-line',
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-ink">{alert.title}</span>
            <Badge tone={critical ? 'danger' : 'warning'} size="sm">
              {formatNumber(alert.count)}
            </Badge>
          </p>
          <p className="mt-0.5 text-sm text-muted">{alert.description}</p>
        </div>
        <RouterLink
          to={toHref(alert.link)}
          className="inline-flex shrink-0 items-center gap-1 rounded-control px-1 text-sm font-medium text-forest-700 hover:underline"
        >
          View
          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        </RouterLink>
      </div>
      {alert.samples.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1 border-t border-line/70 pt-2">
          {alert.samples.map((sample) => (
            <li key={`${sample.label}-${sample.sublabel ?? ''}`} className="text-sm">
              <RouterLink
                to={toHref(sample.link)}
                className="flex flex-wrap items-baseline gap-x-2 rounded-control hover:underline"
              >
                <span className="mono-id text-ink">{sample.label}</span>
                {sample.sublabel && <span className="text-muted">{sample.sublabel}</span>}
              </RouterLink>
            </li>
          ))}
          {alert.count > alert.samples.length && (
            <li className="text-xs text-muted">
              and {formatNumber(alert.count - alert.samples.length)} more
            </li>
          )}
        </ul>
      )}
    </motion.li>
  );
}
