/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0c0f",
        surface: "#111318",
        border: "#2a2d35",
        accent: "#e8c547",
        muted: "#6b7280",
      },
      fontFamily: {
        sans: ["DM Sans", "system-ui", "sans-serif"],
        mono: ["DM Mono", "monospace"],
        display: ["Syne", "sans-serif"],
      },
    },
  },
  plugins: [],
};
