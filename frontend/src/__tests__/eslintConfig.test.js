import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

test('eslint config keeps React rules and recognizes Vitest globals', () => {
  const configPath = resolve(__dirname, '../../eslint.config.mjs');
  const configSource = readFileSync(configPath, 'utf8');

  expect(configSource).toContain('eslint-plugin-react');
  expect(configSource).toContain("vi: 'readonly'");
  expect(configSource).toContain("'dist/**'");
});
