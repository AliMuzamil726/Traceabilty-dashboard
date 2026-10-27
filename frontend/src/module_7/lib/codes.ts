/** Recognising what someone typed or scanned: a code, a bale serial or a trace link. */

export const TOKEN_PATTERN = /^[A-Z2-7]{12}$/;
const TRACE_IN_URL = /\/trace\/([A-Za-z2-7]{12})(?:[/?#]|$)/;

export type CodeInput =
  | { kind: 'url'; token: string; text: string }
  | { kind: 'token'; token: string; text: string }
  | { kind: 'serial'; text: string }
  | { kind: 'empty'; text: string };

/** Classify the input. Serials and lot IDs are left to the server to look up. */
export function classifyCode(raw: string): CodeInput {
  const text = raw.trim();
  if (!text) return { kind: 'empty', text };
  const match = TRACE_IN_URL.exec(text);
  if (match?.[1]) return { kind: 'url', token: match[1].toUpperCase(), text };
  if (TOKEN_PATTERN.test(text.toUpperCase())) return { kind: 'token', token: text.toUpperCase(), text };
  return { kind: 'serial', text: text.toUpperCase() };
}

/** True when phones on the network cannot open the link (localhost or 127.0.0.1). */
export function isLocalBaseUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  try {
    const host = new URL(url).hostname.toLowerCase();
    return host === 'localhost' || host.endsWith('.localhost') || host.startsWith('127.') || host === '[::1]' || host === '0.0.0.0';
  } catch {
    return /localhost|127\.0\.0\.1/i.test(url);
  }
}

export function maskToken(token: string): string {
  return `${token.slice(0, 4)} ${token.slice(4, 8)} ${token.slice(8)}`;
}
