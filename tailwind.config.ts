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
        base: "#0d0c0a",
        panel: "#151411",
        elevated: "#1c1a16",
        hair: "#2a2823",
        ink: {
          DEFAULT: "#ece7dd",
          muted: "#a69f92",
        },
        accent: "#86a6c4",
        gain: "#3fb950",
        loss: "#f85149",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      maxWidth: {
        prose: "70ch",
      },
      typography: {
        invert: {
          css: {
            "--tw-prose-body": "#a69f92",
            "--tw-prose-headings": "#ece7dd",
            "--tw-prose-bold": "#ece7dd",
            "--tw-prose-links": "#86a6c4",
            "--tw-prose-code": "#ece7dd",
            "--tw-prose-quotes": "#a69f92",
            "--tw-prose-bullets": "#2a2823",
            "--tw-prose-hr": "#2a2823",
            "--tw-prose-th-borders": "#2a2823",
            "--tw-prose-td-borders": "#2a2823",
            a: { textDecoration: "none" },
            "a:hover": { textDecoration: "underline" },
            code: {
              fontWeight: "400",
              backgroundColor: "#1c1a16",
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
