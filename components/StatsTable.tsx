import type { Stats } from "@/lib/data";
import { pct, signedPct } from "@/lib/format";

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "gain" | "loss";
}) {
  const color =
    tone === "gain" ? "text-gain" : tone === "loss" ? "text-loss" : "text-ink";
  return (
    <div className="flex flex-col">
      <dt className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        {label}
      </dt>
      <dd className={`num mt-0.5 text-lg ${color}`}>{value}</dd>
    </div>
  );
}

export function StatsTable({ stats }: { stats: Stats }) {
  return (
    <dl className="grid grid-cols-3 gap-4">
      <Stat
        label="CAGR"
        value={signedPct(stats.cagr)}
        tone={stats.cagr >= 0 ? "gain" : "loss"}
      />
      <Stat label="Sharpe" value={stats.sharpe.toFixed(2)} />
      <Stat label="Max DD" value={pct(stats.max_dd)} tone="loss" />
    </dl>
  );
}
