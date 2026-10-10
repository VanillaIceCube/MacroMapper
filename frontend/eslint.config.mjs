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
        ...globals.jest,
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
];
