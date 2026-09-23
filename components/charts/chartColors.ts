// Chart palette — mirrors the design tokens in tailwind.config.ts. Charts are
// imported by client components, so the hex values are duplicated here rather
// than read from Tailwind at runtime. Keep in lockstep with the theme.

export const CHART = {
  ink: "#ece7dd",
  inkMuted: "#a69f92",
  grid: "#2a2823",
  panel: "#151411",
  accent: "#86a6c4",
  benchmark: "#d0ad6a",
  gain: "#3fb950",
  loss: "#f85149",
} as const;

// Categorical palette for the exposure donut — cohesive on the dark canvas,
// distinct enough to read a 6–8 slice breakdown at a glance.
export const EXPOSURE_PALETTE = [
  "#86a6c4", // accent steel
  "#3fb950", // green
  "#e0a84e", // ochre
  "#b48ce8", // violet
  "#56c2c8", // teal
  "#e87fa3", // rose
  "#b5b86a", // olive
  "#9a9387", // warm slate
] as const;
