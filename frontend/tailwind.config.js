/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#C0281F',
          light: '#FEF2F2',
        },
        accent: {
          DEFAULT: '#D97706',
          light: '#FFFBEB',
        },
        surface: {
          page: '#F8F6F3',
          card: '#FFFFFF',
        },
        sidebar: {
          bg: '#1C1C1E',
        },
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
