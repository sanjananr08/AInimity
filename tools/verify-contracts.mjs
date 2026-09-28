#!/usr/bin/env node
/**
 * Lightweight repository check for hosting and judging.
 * It intentionally uses only Node's standard library so it works before npm
 * install and catches the most common integration mistakes early.
 */
import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const read = (name) => readFile(new URL(name, root), 'utf8');
const frontend = await read('frontend/index.html');
const schemas = await read('backend/schemas.py');
const main = await read('backend/main.py');

const checks = [
  ['Evidence Observatory panel', frontend.includes('id="observatory"')],
  ['ChronoForge panel', frontend.includes('id="chronoforge"')],
  ['Evidence API route', main.includes('/api/evidence/assess')],
  ['ChronoForge API route', main.includes('/api/chronoforge/simulate')],
  ['Workspace excludes legacy fact check', !schemas.includes('"fact_check"')],
  ['Workspace excludes legacy scenarios', !schemas.includes('"scenarios"')],
  ['Large document contract', schemas.includes('45000000')],
  ['Safety copy present', frontend.includes('HUMAN REVIEW REQUIRED')],
];

for (const [label, ok] of checks) console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`);
if (checks.some(([, ok]) => !ok)) process.exit(1);
console.log(`\n${checks.length} repository checks passed.`);
