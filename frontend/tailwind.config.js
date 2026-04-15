/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0C0C0F",
        surface: "#131316",
        raised: "#1C1C21",
        border: "#2C2C34",
        accent: "#E54D2E",
        "accent-hover": "#FF5A38",
        muted: "#4C4C58",
        "text-secondary": "#888896",
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
