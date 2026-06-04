"use client";

import type { ExposureSlice } from "@/lib/data";
import { CompositionDonut } from "@/components/charts/CompositionDonut";

// Aggregate sector / asset-class exposure for a secured strategy. Never renders
// tickers — only the grouped weights the contract allows (see
// docs/concepts/open-vs-secured-strategies.md). Draws with the shared
// CompositionDonut primitive.
export function ExposureDonut({
  exposure,
  size = 160,
}: {
  exposure: ExposureSlice[];
  size?: number;
}) {
  if (exposure.length === 0) return null;

  return (
    <CompositionDonut
      heading="Sector exposure"
      slices={exposure.map((e) => ({ label: e.group, value: e.weight }))}
      size={size}
      footnote="Sector breakdown is approximate; unclassified holdings are grouped as “Other.”"
    />
  );
}
