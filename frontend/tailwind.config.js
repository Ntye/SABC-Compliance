/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  // dark: variants activate when <html data-mode="dark"> is set
  darkMode: ['selector', '[data-mode="dark"]'],
  theme: {
    extend: {
      colors: {
        // Brand and accent use RGB triplets so opacity variants (bg-brand/15) work
        brand: {
          DEFAULT: 'rgb(var(--brand-rgb) / <alpha-value>)',
          light: 'var(--brand-light)',
        },
        accent: {
          DEFAULT: 'rgb(var(--accent-rgb) / <alpha-value>)',
          light: 'var(--accent-light)',
        },
        surface: {
          page: 'var(--bg-page)',
          card: 'var(--bg-card)',
        },
        sidebar: {
          bg: 'var(--sidebar-bg)',
        },
        // Console (log output) stays fixed — always dark regardless of theme
        console: {
          bg: '#0C0E0F',
          surface: '#131618',
          text: '#C8D0D4',
          muted: '#5A6268',
          accent: '#00D4AA',
          success: '#2ECC8A',
          warning: '#F0A500',
          danger: '#E05555',
          task: '#0099FF',
        },
      },
      fontFamily: {
        sans: ['DM Sans', 'sans-serif'],
        mono: ['IBM Plex Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
