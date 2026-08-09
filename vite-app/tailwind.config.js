/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'gemini-bg': '#121212',
        'gemini-surface': '#1f1f22',
        'gemini-border': '#333338',
        'gemini-text': '#f4f4f5',
        'gemini-text-secondary': '#a1a1aa',
        'gemini-accent': '#a855f7',
        'gemini-blue-light': '#3b0764',
        'gemini-bot-bg': '#27272a',
        'gemini-user-bg': '#3f3f46',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'Avenir', 'Helvetica', 'Arial', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        }
      }
    },
  },
  plugins: [],
}
