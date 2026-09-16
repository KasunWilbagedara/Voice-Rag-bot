/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
        },
        studio: {
          amber: '#f59e0b',
          gold: '#fbbf24',
          emerald: '#10b981',
          teal: '#14b8a6',
          violet: '#8b5cf6',
          rose: '#f43f5e',
          bronze: '#d97706',
        },
        titanium: {
          50: '#fafafa',
          100: '#f4f4f5',
          200: '#e4e4e7',
          300: '#d4d4d8',
          400: '#a1a1aa',
          500: '#71717a',
          600: '#52525b',
          700: '#3f3f46',
          800: '#27272a',
          850: '#1c1c20',
          900: '#141417',
          950: '#09090b',
        },
        voice: {
          cyan: '#fbbf24',
          emerald: '#10b981',
          violet: '#8b5cf6',
          rose: '#f43f5e',
          sky: '#f59e0b',
          blue: '#d97706',
          amber: '#f59e0b',
        },
        dark: {
          bg: '#08080a',
          card: '#111114',
          cardHover: '#18181c',
          border: 'rgba(255, 255, 255, 0.09)',
          subtle: '#222227',
        },
      },
      boxShadow: {
        'realistic-elevated': '0 20px 40px -15px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.08), inset 0 1px 0 0 rgba(255, 255, 255, 0.12)',
        'realistic-inset': 'inset 0 2px 4px rgba(0, 0, 0, 0.6), inset 0 0 0 1px rgba(0, 0, 0, 0.4)',
        'realistic-btn': '0 4px 12px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.18)',
        'amber-glow': '0 0 25px -4px rgba(245, 158, 11, 0.4)',
        'emerald-glow': '0 0 25px -4px rgba(16, 185, 129, 0.4)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'ripple': 'ripple 2s infinite',
        'float': 'float 4s ease-in-out infinite',
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        ripple: {
          '0%': { transform: 'scale(0.8)', opacity: '1' },
          '100%': { transform: 'scale(2.2)', opacity: '0' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-6px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
    },
  },
  plugins: [],
};
