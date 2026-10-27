import { AlertTriangle, XCircle } from 'lucide-react';
import type { Issue, StepDef } from '../api/types';

export interface WarningListProps {
  issues: Issue[];
  steps: StepDef[];
  onGo?: (stepKey: string) => void;
}

/** Warnings (worth a second look) and errors (must be fixed), grouped under their step. */
export function WarningList({ issues, steps, onGo }: WarningListProps) {
  if (issues.length === 0) return null;
  const title = new Map(steps.map((s) => [s.key, s.title]));
  const label = new Map(steps.flatMap((s) => s.fields.map((f) => [`${s.key}.${f.key}`, f.label] as const)));
  return (
    <ul className="flex flex-col gap-2">
      {issues.map((issue, i) => {
        const error = issue.level === 'error';
        const Icon = error ? XCircle : AlertTriangle;
        return (
          <li key={i} className="flex items-start gap-2 text-sm">
            <Icon className={error ? 'mt-0.5 h-4 w-4 shrink-0 text-danger' : 'mt-0.5 h-4 w-4 shrink-0 text-wheat-600'} aria-hidden />
            <span className="min-w-0 flex-1">
              <span className="font-medium text-ink">
                {title.get(issue.step_key) ?? issue.step_key}
                {issue.entry_index > 0 || steps.find((s) => s.key === issue.step_key)?.repeatable ? `, entry ${issue.entry_index + 1}` : ''}
                {label.get(`${issue.step_key}.${issue.field}`) ? `, ${label.get(`${issue.step_key}.${issue.field}`)}` : ''}
              </span>
              <span className="sr-only">{error ? ' (error)' : ' (warning)'}</span>: <span className="text-muted">{issue.message}</span>
            </span>
            {onGo && (
              <button type="button" className="text-sm font-medium text-forest-700 hover:text-forest-900" onClick={() => onGo(issue.step_key)}>
                Open
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
