#!/usr/bin/env node
/**
 * Brand colour audit. Fails if any colour outside the two brand palettes (Forest,
 * Wheat), the warm neutrals, white, transparent and the single error red appears in
 * the source, the public folder or the built CSS (run `npm run build` first for the
 * built check).
 */
import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs';
import { join, extname, relative } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');

const ALLOWED = new Set(
  [
    // Forest & SAWiE Brand Green
    '00A651', '0B2418', '10331F', '164A2C', '1D6039', '25774A', '2F915A', 'E3F1E8', 'F1F8F3',
    // Wheat
    'A67C1F', 'C79A2E', 'E3C479', 'F7EBCB', 'FBF5E4',
    // Neutrals
    'F5F6F2', 'FFFFFF', 'E3E6DE', '5B675F', '15221B',
    // Error red and tint
    'B42318', 'FDECEA',
  ].map((h) => h.toUpperCase()),
);

function normalizeHex(raw) {
  let h = raw.replace('#', '').toUpperCase();
  if (h.length === 3 || h.length === 4) h = [...h].map((c) => c + c).join('');
  const alpha = h.length === 8 ? h.slice(6) : 'FF';
  return { rgb: h.slice(0, 6), transparent: alpha === '00' };
}

function rgbToHex(r, g, b) {
  return [r, g, b].map((n) => Number(n).toString(16).padStart(2, '0')).join('').toUpperCase();
}

function scanText(text) {
  const bad = [];
  for (const m of text.matchAll(/#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b/g)) {
    const { rgb, transparent } = normalizeHex(m[0]);
    if (!transparent && rgb !== '000000' && !ALLOWED.has(rgb)) bad.push(m[0]);
    if (rgb === '000000' && !transparent) bad.push(m[0]);
  }
  for (const m of text.matchAll(/rgba?\(\s*(\d{1,3})[\s,]+(\d{1,3})[\s,]+(\d{1,3})\s*(?:[,/]\s*([\d.]+%?|var\([^)]*\)))?/g)) {
    const hex = rgbToHex(m[1], m[2], m[3]);
    const alpha = m[4];
    const invisible = alpha === '0' || alpha === '0%';
    if (!invisible && !ALLOWED.has(hex)) bad.push(m[0]);
  }
  // Tailwind default palette names should never appear in class names.
  for (const m of text.matchAll(/\b(?:bg|text|border|ring|fill|stroke|from|via|to|outline|shadow|accent|decoration|divide)-(?:slate|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|black)-\d{2,3}\b/g)) {
    bad.push(m[0]);
  }
  return bad;
}

function walk(dir, exts, out = []) {
  if (!existsSync(dir)) return out;
  for (const name of readdirSync(dir)) {
    if (name === 'node_modules') continue;
    const full = join(dir, name);
    if (statSync(full).isDirectory()) walk(full, exts, out);
    else if (exts.includes(extname(name))) out.push(full);
  }
  return out;
}

const files = [
  ...walk(join(ROOT, 'src'), ['.ts', '.tsx', '.css']),
  ...walk(join(ROOT, 'public'), ['.svg', '.html']),
  join(ROOT, 'index.html'),
  join(ROOT, 'tailwind.config.ts'),
  ...walk(join(ROOT, 'dist', 'assets'), ['.css']),
].filter((f) => !f.includes('check-colors'));

let failures = 0;
for (const file of files) {
  const bad = scanText(readFileSync(file, 'utf8'));
  if (bad.length) {
    failures += bad.length;
    console.error(`${relative(ROOT, file)}: ${[...new Set(bad)].join(', ')}`);
  }
}
const builtChecked = existsSync(join(ROOT, 'dist', 'assets'));
if (failures) {
  console.error(`\nColour audit failed: ${failures} off-brand colour(s).`);
  process.exit(1);
}
console.log(`Colour audit passed: ${files.length} files${builtChecked ? ' (including built CSS)' : ''}, only Forest, Wheat, warm neutrals and the error red.`);
