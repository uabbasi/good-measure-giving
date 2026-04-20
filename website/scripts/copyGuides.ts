/**
 * Copies guide JSON files from data/guides/ to public/data/guides/
 * so they're served at /data/guides/:slug.json at runtime.
 */
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SRC = path.join(__dirname, '../data/guides');
const DST = path.join(__dirname, '../public/data/guides');

if (!fs.existsSync(SRC)) {
  console.log('No guides source directory; skipping copy.');
  process.exit(0);
}

fs.mkdirSync(DST, { recursive: true });
const files = fs.readdirSync(SRC).filter((f) => f.endsWith('.json'));
for (const f of files) {
  fs.copyFileSync(path.join(SRC, f), path.join(DST, f));
}
console.log(`Copied ${files.length} guide files to ${path.relative(process.cwd(), DST)}`);
