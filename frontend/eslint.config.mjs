import js from '@eslint/js';
import eslintReact from '@eslint-react/eslint-plugin';
import jsxA11y from 'eslint-plugin-jsx-a11y-x';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';

export default [
  {
    ignores: ['coverage/**', 'dist/**', 'node_modules/**'],
  },
  js.configs.recommended,
  eslintReact.configs.recommended,
  reactHooks.configs.flat['recommended-latest'],
  {
    ...jsxA11y.configs.recommended,
  },
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.vitest,
        vi: 'readonly',
      },
    },
    rules: {
      // Keep the migration behavior-neutral; revisit these stricter rules separately.
      '@eslint-react/no-array-index-key': 'off',
      '@eslint-react/purity': 'off',
      '@eslint-react/set-state-in-effect': 'off',
      'jsx-a11y-x/no-autofocus': 'off',
      'no-unused-vars': [
        'error',
        { varsIgnorePattern: '^_', argsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' },
      ],
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/immutability': 'off',
      'no-loss-of-precision': 'warn',
      'logical-assignment-operators': 'off',
      'preserve-caught-error': 'off',
    },
  },
  {
    files: ['src/**/*.js'],
    rules: {
      'no-restricted-syntax': [
        'error',
        { selector: 'Program:has(JSXElement, JSXFragment)', message: 'Use .jsx for JSX markup.' },
      ],
    },
  },
  {
    files: ['src/[A-Z]*.js', 'src/{components,pages}/**/[A-Z]*.js', 'src/**/use[A-Z0-9]*.jsx'],
    ignores: ['**/*.test.{js,jsx}'],
    rules: {
      'no-restricted-syntax': [
        'error',
        { selector: 'Program', message: 'Use .jsx for React components and .js for hooks.' },
      ],
    },
  },
];
