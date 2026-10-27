import type { Config } from 'tailwindcss';

/**
 * The palette REPLACES Tailwind's defaults on purpose: only the two brand colours
 * (forest, wheat), the warm neutrals and the single error red exist, so an
 * off-brand class (any default Tailwind hue) simply does not compile.
 * Values mirror src/design-system/tokens.css.
 */
const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      white: '#FFFFFF',
      forest: {
        950: '#0B2418',
        900: '#10331F',
        800: '#164A2C',
        700: '#1D6039',
        600: '#25774A',
        500: '#2F915A',
        100: '#E3F1E8',
        50: '#F1F8F3',
      },
      wheat: {
        600: '#A67C1F',
        500: '#C79A2E',
        300: '#E3C479',
        100: '#F7EBCB',
        50: '#FBF5E4',
      },
      canvas: '#F5F6F2',
      surface: '#FFFFFF',
      line: '#E3E6DE',
      muted: '#5B675F',
      ink: '#15221B',
      danger: { DEFAULT: '#B42318', tint: '#FDECEA' },
      // Aliases only: Tailwind's preflight reads gray.200 (default border) and
      // gray.400 (placeholder). They point at the warm neutrals, not new hues.
      gray: { 200: '#E3E6DE', 400: '#5B675F' },
    },
    ringColor: ({ theme }) => ({ DEFAULT: theme('colors.forest.500'), ...theme('colors') }),
    fontFamily: {
      sans: ['"Inter Variable"', 'Inter', 'system-ui', 'Segoe UI', 'sans-serif'],
      mono: ['"JetBrains Mono"', 'ui-monospace', 'Consolas', 'monospace'],
    },
    fontSize: {
      xs: ['12px', { lineHeight: '16px' }],
      sm: ['13px', { lineHeight: '18px' }],
      base: ['14px', { lineHeight: '20px' }],
      md: ['16px', { lineHeight: '24px' }],
      lg: ['20px', { lineHeight: '28px' }],
      xl: ['24px', { lineHeight: '32px' }],
      '2xl': ['32px', { lineHeight: '40px' }],
    },
    borderRadius: {
      none: '0',
      sm: '4px',
      DEFAULT: '8px',
      control: '8px',
      card: '10px',
      pill: '999px',
      full: '9999px',
    },
    boxShadow: {
      none: 'none',
      1: '0 1px 2px rgba(11, 36, 24, 0.04), 0 1px 1px rgba(11, 36, 24, 0.03)',
      2: '0 8px 24px -8px rgba(11, 36, 24, 0.12), 0 2px 6px rgba(11, 36, 24, 0.05)',
    },
    extend: {
      transitionTimingFunction: { brand: 'cubic-bezier(.2,.8,.2,1)' },
      transitionDuration: { fast: '120ms', base: '200ms', slow: '320ms' },
      width: { rail: '68px', sidebar: '228px' },
      keyframes: {
        shimmer: { '100%': { transform: 'translateX(100%)' } },
      },
      animation: { shimmer: 'shimmer 1.4s cubic-bezier(.2,.8,.2,1) infinite' },
    },
  },
  plugins: [],
};

export default config;
