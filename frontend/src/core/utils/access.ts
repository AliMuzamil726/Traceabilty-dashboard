import type { Role } from '@/core/api/types';

/**
 * Pages a field officer may open: their own home screen, their two modules and their
 * profile. Staff open everything except Settings; an administrator everything.
 */
const OFFICER_PATHS = ['/', '/register', '/fieldbook', '/profile'] as const;

function matches(pathname: string, base: string): boolean {
  return pathname === base || pathname.startsWith(`${base}/`);
}

/** May this role open this path (a module path such as `/radar`, or any page below it)? */
export function canOpen(role: Role | undefined, pathname: string): boolean {
  if (!role) return false;
  if (role === 'admin') return true;
  if (role === 'staff') return !matches(pathname, '/settings');
  return OFFICER_PATHS.some((p) => matches(pathname, p));
}

/**
 * Search and the signed-in person's menu sit on the dashboard home screen only, and
 * never for a field officer. Sign out is in the sidebar, so it stays reachable.
 */
export function showsTopbarTools(role: Role | undefined, pathname: string): boolean {
  return pathname === '/' && role !== 'officer' && canOpen(role, '/');
}
