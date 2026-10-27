#!/usr/bin/env node
/**
 * Used by frontend.bat. Exit code 0 when `url` answers with HTTP 2xx within the
 * timeout (and, if given, the body contains `mustContain`); 1 otherwise.
 *
 *   node scripts/probe.mjs http://127.0.0.1:8000/api/health
 *   node scripts/probe.mjs http://localhost:5173/ SAWIE
 */
const [, , url, mustContain] = process.argv;
if (!url) {
  console.error('usage: probe.mjs <url> [mustContain]');
  process.exit(2);
}

const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), 1500);
try {
  const response = await fetch(url, { signal: controller.signal });
  const body = mustContain ? await response.text() : '';
  process.exit(response.ok && (!mustContain || body.includes(mustContain)) ? 0 : 1);
} catch {
  process.exit(1);
} finally {
  clearTimeout(timer);
}
