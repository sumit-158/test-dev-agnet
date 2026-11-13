/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        asm: {
          ink: "#1A1F36",
          navy: "#003B5C",
          blue: "#0E5CAD",
          cyan: "#00B4D8",
          mist: "#E6EEF5",
          paper: "#F7F9FC",
          line: "#D7DEE8",
          muted: "#6B7280",
          ok: "#10B981",
          warn: "#F59E0B",
          err: "#EF4444",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.10)",
      },
    },
  },
  plugins: [],
};
