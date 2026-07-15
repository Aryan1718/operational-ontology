import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#f4efe5",
        ink: "#1d1a16",
        accent: "#a44c24",
        accentSoft: "#e5c7b9",
        border: "#d3c6b8",
      },
      fontFamily: {
        sans: ["'Source Sans 3'", "sans-serif"],
        display: ["'Space Grotesk'", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
