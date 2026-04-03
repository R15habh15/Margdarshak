/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        surface:  '#0d1117',
        panel:    '#161b22',
        border:   '#21262d',
        accent:   '#00e5ff',
        success:  '#00ff9d',
        warning:  '#ffb700',
        danger:   '#ff4444',
        muted:    '#8b949e',
      },
      fontFamily: {
        display: ['"Rajdhani"', 'sans-serif'],
        mono:    ['"JetBrains Mono"', 'monospace'],
        body:    ['"DM Sans"', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
