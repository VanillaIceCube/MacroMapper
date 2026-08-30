import js from '@eslint/js';
import { fixupConfigRules, fixupPluginRules } from '@eslint/compat';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';

export default [
  {
    ignores: ['coverage/**', 'dist/**', 'node_modules/**'],
  },
  js.configs.recommended,
  ...fixupConfigRules(react.configs.flat.recommended),
  ...fixupConfigRules(react.configs.flat['jsx-runtime']),
  reactHooks.configs.flat['recommended-latest'],
  {
    ...jsxA11y.flatConfigs.recommended,
    plugins: {
      'jsx-a11y': fixupPluginRules(jsxA11y),
    },
  },
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.jest,
        vi: 'readonly',
      },
    },
    settings: {
      react: {
        version: 'detect',
      },
    },
    rules: {
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      'jsx-a11y/no-autofocus': 'off',
      'no-unused-vars': ['error', { varsIgnorePattern: '^_', argsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' }],
      'react-hooks/set-state-in-effect': 'off',
      'no-loss-of-precision': 'warn',
      'logical-assignment-operators': 'off',
      'preserve-caught-error': 'off',
    },
  },
];
