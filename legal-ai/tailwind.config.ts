import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#07111f",
          900: "#0b1b30",
          800: "#13263f",
          700: "#1d3553",
        },
        crimson: {
          600: "#b3122f",
          500: "#c8102e",
          400: "#e23a4d",
        },
        saffron: {
          500: "#d4a017",
          400: "#e6b84a",
        },
        parchment: {
          50: "#fbf7ef",
          100: "#f4ecdc",
          200: "#e7d8b8",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "Source Serif 4", "serif"],
        sans: ["var(--font-sans)", "IBM Plex Sans", "Noto Sans Devanagari", "sans-serif"],
        devanagari: ["var(--font-deva)", "Noto Sans Devanagari", "sans-serif"],
      },
      boxShadow: {
        folio: "0 24px 60px rgba(7, 17, 31, 0.28)",
      },
    },
  },
  plugins: [],
};

export default config;
