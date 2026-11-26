import type { Config } from "tailwindcss";

// ASM design tokens (skill ui_ux_design §3).
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
    },
  },
  plugins: [],
} satisfies Config;
