import js from '@eslint/js';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

const MODULES = [1, 2, 3, 4, 5, 6, 7, 8];

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'coverage'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      'jsx-a11y': jsxA11y,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.flatConfigs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      '@typescript-eslint/consistent-type-imports': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'no-console': ['error', { allow: ['warn', 'error'] }],
    },
  },
  // Module isolation: a module may only import another module through its index.ts.
  ...MODULES.map((n) => ({
    files: [`src/module_${n}/**/*.{ts,tsx}`],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: MODULES.filter((m) => m !== n).map((m) => ({
            group: [`@/module_${m}/*`, `**/module_${m}/*`],
            message: `Import module_${m} only through '@/module_${m}' (its index.ts).`,
          })),
        },
      ],
    },
  })),
  {
    files: ['src/**/*.test.{ts,tsx}', 'src/test/**'],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: { 'react-refresh/only-export-components': 'off' },
  },
  {
    files: ['scripts/**/*.mjs', '*.config.{js,ts}', 'e2e/**/*.ts'],
    languageOptions: { globals: globals.node },
  },
);
