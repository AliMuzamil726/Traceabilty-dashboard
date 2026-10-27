/** Date helpers. The API speaks ISO 8601 in UTC; the UI shows local dates. */

/** Today as YYYY-MM-DD in the user's local time zone. */
export function todayIsoDate(now: Date = new Date()): string {
  return toIsoDate(now);
}

/** Local calendar date of `date` as YYYY-MM-DD. */
export function toIsoDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/** Parse YYYY-MM-DD as a local date (not UTC midnight). Returns null when invalid. */
export function parseIsoDate(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const [, y, m, d] = match.map(Number) as [number, number, number, number];
  const date = new Date(y, m - 1, d);
  return date.getFullYear() === y && date.getMonth() === m - 1 && date.getDate() === d ? date : null;
}

export function addDays(date: Date, days: number): Date {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}

/** Whole days from a to b (b - a), ignoring time of day. */
export function daysBetween(a: Date, b: Date): number {
  const start = Date.UTC(a.getFullYear(), a.getMonth(), a.getDate());
  const end = Date.UTC(b.getFullYear(), b.getMonth(), b.getDate());
  return Math.round((end - start) / 86_400_000);
}

/** Cotton and hemp seasons both fit inside one calendar year in this phase. */
export function seasonYear(date: Date = new Date()): number {
  return date.getFullYear();
}

/** "in 3 days", "2 days ago", "today" */
export function relativeDays(target: Date, now: Date = new Date()): string {
  const diff = daysBetween(now, target);
  if (diff === 0) return 'today';
  if (diff === 1) return 'tomorrow';
  if (diff === -1) return 'yesterday';
  return diff > 0 ? `in ${diff} days` : `${Math.abs(diff)} days ago`;
}
