/**
 * Copies guide JSON files from data/guides/ to public/data/guides/
 * so they're served at /data/guides/:slug.json at runtime.
 *
 * Publication gate: guides marked status: 'pending-review' in guides.json
 * are NOT copied, and the public guides.json index is written with those
 * entries filtered out — so they're invisible at runtime (the index page
 * never lists them and direct navigation 404s) until they clear review.
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

interface GuideIndexEntry {
  slug: string;
  status?: 'published' | 'pending-review';
}

const indexPath = path.join(SRC, 'guides.json');
const index = JSON.parse(fs.readFileSync(indexPath, 'utf-8'));
const all: GuideIndexEntry[] = index.guides || [];
const published = all.filter((g) => g.status !== 'pending-review');
const held = all.filter((g) => g.status === 'pending-review');

fs.mkdirSync(DST, { recursive: true });

// Start from a clean slate so previously-copied (now held) guides disappear.
for (const f of fs.readdirSync(DST).filter((f) => f.endsWith('.json'))) {
  fs.unlinkSync(path.join(DST, f));
}

// Filtered index — the runtime index page reads this.
fs.writeFileSync(
  path.join(DST, 'guides.json'),
  JSON.stringify({ guides: published.map(({ status: _status, ...rest }) => rest) }, null, 2),
  'utf-8'
);

// Detail files for published guides only.
let copied = 0;
for (const g of published) {
  const src = path.join(SRC, `${g.slug}.json`);
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, path.join(DST, `${g.slug}.json`));
    copied++;
  }
}

console.log(
  `Copied ${copied} published guide(s) to ${path.relative(process.cwd(), DST)}` +
    (held.length ? `; held back ${held.length} pending review: ${held.map((g) => g.slug).join(', ')}` : '')
);
