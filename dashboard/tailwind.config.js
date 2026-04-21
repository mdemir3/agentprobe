/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"DM Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        probe: {
          50: '#f0fdf6',
          100: '#d9f7e5',
          200: '#b5edcc',
          300: '#7fdda9',
          400: '#47c57f',
          500: '#22a963',
          600: '#168a4f',
          700: '#146d41',
          800: '#145736',
          900: '#12472e',
          950: '#042718',
        },
        surface: {
          0: '#0a0e14',
          1: '#111820',
          2: '#1a222d',
          3: '#232d3a',
          4: '#2d3848',
        },
        verdict: {
          supported: '#22c55e',
          refuted: '#ef4444',
          notfound: '#f59e0b',
          review: '#8b5cf6',
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out forwards',
        'slide-up': 'slideUp 0.4s ease-out forwards',
        'pulse-slow': 'pulse 3s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};
