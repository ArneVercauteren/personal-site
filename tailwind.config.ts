import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

// Tokens mirror docs/reference/design-system.md — keep the two in lockstep.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./content/**/*.{md,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        base: "#0a0c10",
        panel: "#11151c",
        elevated: "#161b22",
        hair: "#222a35",
        ink: {
          DEFAULT: "#e6edf3",
          muted: "#9da7b3",
        },
        accent: "#39d0d8",
        gain: "#3fb950",
        loss: "#f85149",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      maxWidth: {
        prose: "70ch",
      },
      typography: {
        invert: {
          css: {
            "--tw-prose-body": "#9da7b3",
            "--tw-prose-headings": "#e6edf3",
            "--tw-prose-bold": "#e6edf3",
            "--tw-prose-links": "#39d0d8",
            "--tw-prose-code": "#e6edf3",
            "--tw-prose-quotes": "#9da7b3",
            "--tw-prose-bullets": "#222a35",
            "--tw-prose-hr": "#222a35",
            "--tw-prose-th-borders": "#222a35",
            "--tw-prose-td-borders": "#222a35",
            a: { textDecoration: "none" },
            "a:hover": { textDecoration: "underline" },
            code: {
              fontWeight: "400",
              backgroundColor: "#161b22",
              padding: "0.1em 0.35em",
              borderRadius: "0.25rem",
            },
            "code::before": { content: '""' },
            "code::after": { content: '""' },
          },
        },
      },
    },
  },
  plugins: [typography],
};

export default config;
