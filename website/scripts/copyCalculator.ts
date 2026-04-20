/**
 * Copies zakat calculator JSON from data/zakat-calculator/ to
 * public/data/zakat-calculator/ so runtime fetch can read it.
 */
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SRC = path.join(__dirname, '../data/zakat-calculator');
const DST = path.join(__dirname, '../public/data/zakat-calculator');

if (!fs.existsSync(SRC)) {
  console.log('No zakat-calculator source directory; skipping copy.');
  process.exit(0);
}

fs.mkdirSync(DST, { recursive: true });
const files = fs.readdirSync(SRC).filter((f) => f.endsWith('.json'));
for (const f of files) {
  fs.copyFileSync(path.join(SRC, f), path.join(DST, f));
}
console.log(`Copied ${files.length} calculator files to ${path.relative(process.cwd(), DST)}`);
