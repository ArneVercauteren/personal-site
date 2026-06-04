// Chart palette — mirrors the design tokens in tailwind.config.ts. Charts are
// imported by client components, so the hex values are duplicated here rather
// than read from Tailwind at runtime. Keep in lockstep with the theme.

export const CHART = {
  ink: "#e6edf3",
  inkMuted: "#9da7b3",
  grid: "#222a35",
  panel: "#11151c",
  accent: "#39d0d8",
  benchmark: "#e8b84c",
  gain: "#3fb950",
  loss: "#f85149",
} as const;

// Categorical palette for the exposure donut — cohesive on the dark canvas,
// distinct enough to read a 6–8 slice breakdown at a glance.
export const EXPOSURE_PALETTE = [
  "#39d0d8", // accent cyan
  "#3fb950", // green
  "#6e9fed", // blue
  "#b48ce8", // violet
  "#e8b84c", // amber
  "#f0883e", // orange
  "#56c2c8", // teal
  "#8b97a5", // slate
] as const;
