import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

test('eslint config keeps React rules and recognizes Vitest globals', () => {
  const eslintConfig = require('../../.eslintrc.js');

  expect(eslintConfig.extends).toEqual(['react-app', 'react-app/jest']);
  expect(eslintConfig.globals.vi).toBe('readonly');
  expect(eslintConfig.ignorePatterns).toContain('dist/**');
});
