#!/usr/bin/env node
/** Print the SHA-256 of a file (used by frontend.bat to detect lockfile changes). */
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

const file = process.argv[2];
try {
  process.stdout.write(createHash('sha256').update(readFileSync(file)).digest('hex'));
} catch {
  process.stdout.write('missing');
}
