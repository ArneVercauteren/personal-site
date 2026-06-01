import type { EquityPoint } from "@/lib/data";

// Dependency-free SVG equity sparkline. Recharts is the planned upgrade for the
// full equity / drawdown / exposure charts (see docs/subsystems/live-dashboard.md).
export function Sparkline({
  points,
  width = 480,
  height = 96,
}: {
  points: EquityPoint[];
  width?: number;
  height?: number;
}) {
  if (points.length < 2) return null;

  const values = points.map((p) => p.v);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pad = 4;

  const coords = points.map((p, i) => {
    const x = (i / (points.length - 1)) * (width - pad * 2) + pad;
    const y = height - pad - ((p.v - min) / span) * (height - pad * 2);
    return [x, y] as const;
  });

  const line = coords.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
  const up = values[values.length - 1] >= values[0];
  const stroke = up ? "#3fb950" : "#f85149";
  const areaId = `spark-${points[0].d}-${points[points.length - 1].d}`;

  const area = `${line} ${coords[coords.length - 1][0].toFixed(2)},${height} ${coords[0][0].toFixed(2)},${height}`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height={height}
      preserveAspectRatio="none"
      role="img"
      aria-label="Equity curve"
    >
      <defs>
        <linearGradient id={areaId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.22" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#${areaId})`} />
      <polyline
        points={line}
        fill="none"
        stroke={stroke}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
