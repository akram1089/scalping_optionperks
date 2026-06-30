/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#FAFBFC',
        surface: '#FFFFFF',
        'bg-subtle': '#F4F6F9',
        border: '#E8ECF1',
        'border-strong': '#D1D9E6',
        text: '#0B1220',
        'text-muted': '#64748B',
        'text-faint': '#94A3B8',
        primary: { DEFAULT: '#2563EB', 700: '#1D4ED8', 50: '#EFF6FF' },
        'primary-navy': '#0F172A',
        accent: { DEFAULT: '#16A34A', 700: '#15803D', 50: '#F0FDF4' },
        up: '#16A34A',
        down: '#DC2626',
        warn: '#D97706',
        sidebar: '#FFFFFF',
      },
      borderRadius: {
        btn: '10px',
        card: '14px',
        pill: '999px',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Syne', 'Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(15,23,42,.04), 0 4px 16px rgba(15,23,42,.06)',
        elevated: '0 8px 32px rgba(15,23,42,.08)',
        sidebar: '1px 0 0 rgba(15,23,42,.06)',
      },
      backgroundImage: {
        grid: 'linear-gradient(rgba(15,23,42,.03) 1px, transparent 1px), linear-gradient(90deg, rgba(15,23,42,.03) 1px, transparent 1px)',
      },
      backgroundSize: {
        grid: '48px 48px',
      },
    },
  },
  plugins: [],
}
