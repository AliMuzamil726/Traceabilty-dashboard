/**
 * The server decides where a figure takes you; this turns that into a route.
 *
 * Every count, stage and alert carries a `Link` of a path plus the query keys the
 * target page reads. Building the address here, from what the server sent, keeps the
 * dashboard from holding a second copy of every module's filter names.
 */
import type { Link } from '../api/types';

export function toHref(link: Link): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(link.params)) {
    if (value !== '') params.set(key, value);
  }
  const query = params.toString();
  return query ? `${link.path}?${query}` : link.path;
}
