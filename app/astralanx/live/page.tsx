import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { Disclaimer } from "@/components/Disclaimer";
import { StrategyCard } from "@/components/StrategyCard";
import { loadManifest, loadSnapshotBenchmark, loadStrategyIndex } from "@/lib/data";
import { shortDate } from "@/lib/format";

export const metadata: Metadata = {
  title: "Live paper strategies",
  description: "Forward paper returns, drawdowns, schedules, allocations, and audited update freshness.",
  alternates: { canonical: "/astralanx/live" },
};

export default function LivePage() {
  const portfolio = loadStrategyIndex();
  const manifest = loadManifest();
  const sp500 = loadSnapshotBenchmark();

  const open = portfolio.strategies.filter((s) => s.visibility === "open");
  const secured = portfolio.strategies.filter((s) => s.visibility === "secured");

  return (
    <div>
      <PageHeader
        eyebrow="Live · simulated"
        title="Paper-trading dashboard"
        intro="A few Astralanx strategies run as a simulated portfolio. Open-formula strategies show the full basket, end to end; the rest show performance and aggregate sector exposure only. Where a curve predates the “Live” marker, that earlier stretch is an out-of-sample backtest of the same frozen formula — live paper-trading begins at the marker."
      />

      <div className="mb-6">
        <Disclaimer />
      </div>

      <p className="mb-10 font-mono text-xs text-ink-muted">
        Snapshot as of{" "}
        <span className="text-ink">{shortDate(portfolio.as_of)}</span> ·{" "}
        {portfolio.base_currency} ·{" "}
        <span className="text-gain">validated</span>{" "}
        · snapshot {manifest.snapshot_id.slice(0, 8)}
      </p>

      <section>
        <div className="mb-4 border-b border-hair pb-3">
          <h2 className="text-xl font-semibold tracking-tight text-ink">
            Open strategies
          </h2>
          <p className="mt-1 text-sm text-ink-muted">
            Formula and full position list published, all stats are shown.
          </p>
        </div>
        {open.length > 0 ? (
          <div className="grid gap-5 lg:grid-cols-2">
            {open.map((s) => (
              <StrategyCard
                key={s.id}
                summary={s}
                benchmark={sp500}
              />
            ))}
          </div>
        ) : (
          <p className="text-sm text-ink-muted">No open strategies yet.</p>
        )}
      </section>

      <section className="mt-12">
        <div className="mb-4 border-b border-hair pb-3">
          <h2 className="text-xl font-semibold tracking-tight text-ink">
            Secured strategies
          </h2>
          <p className="mt-1 text-sm text-ink-muted">
            Performance and aggregate sector exposure only.
          </p>
        </div>
        {secured.length > 0 ? (
          <div className="grid gap-5 lg:grid-cols-2">
            {secured.map((s) => (
              <StrategyCard
                key={s.id}
                summary={s}
                benchmark={sp500}
              />
            ))}
          </div>
        ) : (
          <p className="text-sm text-ink-muted">No secured strategies yet.</p>
        )}
      </section>
    </div>
  );
}
