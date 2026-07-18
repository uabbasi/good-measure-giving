/**
 * Data sync script (copy-only).
 *
 * data-pipeline/export.py is the single writer of website/data/**. This script
 * no longer rebuilds charities.json, no longer generates src/data/charities.ts
 * or src/data/topCharity.ts, and applies no display transformations. It:
 *   1. Validates that the committed index parses and is non-empty.
 *   2. Mirrors website/data/** → website/public/data/** wholesale so Vite
 *      serves it at /data/* (dev) and copies it into dist/data/* (build).
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DATA_DIR = path.join(__dirname, '../data');
const PUBLIC_DATA_DIR = path.join(__dirname, '../public/data');
const CHARITIES_JSON = path.join(DATA_DIR, 'charities.json');
const CHARITY_FILES_DIR = path.join(DATA_DIR, 'charities');

function countFiles(dir: string): number {
  let count = 0;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    count += entry.isDirectory() ? countFiles(full) : 1;
  }
  return count;
}

function main() {
  console.log('🔄 Syncing website/data → website/public/data (copy-only)...\n');

  // Guard: the served index must parse and be non-empty.
  const index = JSON.parse(fs.readFileSync(CHARITIES_JSON, 'utf-8'));
  const charities = Array.isArray(index) ? index : index.charities;
  if (!Array.isArray(charities) || charities.length === 0) {
    throw new Error(`charities.json is invalid or empty: ${CHARITIES_JSON}`);
  }
  const detailCount = fs
    .readdirSync(CHARITY_FILES_DIR)
    .filter((f) => f.startsWith('charity-') && f.endsWith('.json')).length;
  console.log(`📋 charities.json OK: ${charities.length} charities (${detailCount} detail files)`);

  // Wholesale one-directional mirror.
  fs.rmSync(PUBLIC_DATA_DIR, { recursive: true, force: true });
  fs.cpSync(DATA_DIR, PUBLIC_DATA_DIR, { recursive: true });

  console.log(`📂 Copied ${countFiles(PUBLIC_DATA_DIR)} files → ${PUBLIC_DATA_DIR}`);
}

main();
