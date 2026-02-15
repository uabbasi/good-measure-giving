import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const INPUT_YAML = path.resolve(__dirname, '../../data-pipeline/config/ui_signals.yaml');
const OUTPUT_TS = path.resolve(__dirname, '../src/generated/uiSignalsConfig.ts');

function parseScalar(raw) {
  const value = raw.trim();
  if (value === 'null') return null;
  if (value === 'true') return true;
  if (value === 'false') return false;
  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
    return value.slice(1, -1);
  }
  if (value.startsWith('[') && value.endsWith(']')) {
    try {
      return JSON.parse(value.replaceAll("'", '"'));
    } catch {
      return [];
    }
  }
  if (/^-?\d+(\.\d+)?$/.test(value)) {
    return Number(value);
  }
  return value;
}

function parseSimpleYaml(source) {
  const root = {};
  const stack = [{ indent: -1, obj: root }];
  const lines = source.split('\n');

  for (const rawLine of lines) {
    const withoutComment = rawLine.replace(/\s+#.*$/, '');
    if (!withoutComment.trim()) continue;
    const indent = withoutComment.match(/^ */)?.[0].length ?? 0;
    const line = withoutComment.trim();

    while (stack.length > 1 && indent <= stack[stack.length - 1].indent) {
      stack.pop();
    }

    const parent = stack[stack.length - 1].obj;
    if (line.endsWith(':')) {
      const key = line.slice(0, -1).trim();
      const child = {};
      parent[key] = child;
      stack.push({ indent, obj: child });
      continue;
    }

    const idx = line.indexOf(':');
    if (idx === -1) continue;
    const key = line.slice(0, idx).trim();
    const valueRaw = line.slice(idx + 1).trim();
    parent[key] = parseScalar(valueRaw);
  }

  return root;
}

function sortDeep(value) {
  if (Array.isArray(value)) return value.map(sortDeep);
  if (value && typeof value === 'object') {
    const entries = Object.entries(value).sort(([a], [b]) => a.localeCompare(b));
    const sorted = {};
    for (const [key, val] of entries) {
      sorted[key] = sortDeep(val);
    }
    return sorted;
  }
  return value;
}

function computeHash(config) {
  const canonical = JSON.stringify(sortDeep(config));
  return `sha256:${crypto.createHash('sha256').update(canonical, 'utf8').digest('hex')}`;
}

function generateOutput(config, hash) {
  const rendered = JSON.stringify(config, null, 2);
  const version = typeof config.config_version === 'string' ? config.config_version : 'unknown';
  return `/**
 * Auto-generated from data-pipeline/config/ui_signals.yaml
 * Do not edit manually.
 */

export const uiSignalsConfig = ${rendered} as const;
export const UI_SIGNALS_CONFIG_VERSION = ${JSON.stringify(version)};
export const UI_SIGNALS_CONFIG_HASH = ${JSON.stringify(hash)};
`;
}

function main() {
  if (!fs.existsSync(INPUT_YAML)) {
    throw new Error(`Missing input config: ${INPUT_YAML}`);
  }

  const raw = fs.readFileSync(INPUT_YAML, 'utf8');
  const parsed = parseSimpleYaml(raw);
  const hash = computeHash(parsed);
  const output = generateOutput(parsed, hash);

  fs.mkdirSync(path.dirname(OUTPUT_TS), { recursive: true });
  fs.writeFileSync(OUTPUT_TS, output, 'utf8');
  process.stdout.write(`Synced ui_signals config -> ${path.relative(process.cwd(), OUTPUT_TS)}\n`);
}

main();
