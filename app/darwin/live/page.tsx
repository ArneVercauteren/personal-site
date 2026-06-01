import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { Disclaimer } from "@/components/Disclaimer";
import { StrategyCard } from "@/components/StrategyCard";
import { loadPortfolio, loadStrategyMeta, isOpen } from "@/lib/data";
import { shortDate } from "@/lib/format";

export const metadata: Metadata = { title: "Live" };

export default function LivePage() {
  const portfolio = loadPortfolio();
  const metaById = new Map(
    loadStrategyMeta().strategies.map((m) => [m.id, m]),
  );

  const open = portfolio.strategies.filter(isOpen);
  const secured = portfolio.strategies.filter((s) => !isOpen(s));

  return (
    <div>
      <PageHeader
        eyebrow="Live · simulated"
        title="Paper-trading dashboard"
        intro="A few Darwin strategies run as a simulated portfolio. Open-formula strategies show the full basket, end to end; the rest show performance and aggregate sector exposure only."
      />

      <div className="mb-6">
        <Disclaimer />
      </div>

      <p className="mb-10 font-mono text-xs text-ink-muted">
        Snapshot as of{" "}
        <span className="text-ink">{shortDate(portfolio.as_of)}</span> ·{" "}
        {portfolio.base_currency}
      </p>

      <section>
        <div className="mb-4 border-b border-hair pb-3">
          <h2 className="text-xl font-semibold tracking-tight text-ink">
            Open strategies
          </h2>
          <p className="mt-1 text-sm text-ink-muted">
            Formula and full position list published — everything is shown.
          </p>
        </div>
        {open.length > 0 ? (
          <div className="grid gap-5 lg:grid-cols-2">
            {open.map((s) => (
              <StrategyCard key={s.id} strategy={s} meta={metaById.get(s.id)} />
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
            Performance and aggregate sector exposure only — the formula and
            individual weights stay private.
          </p>
        </div>
        {secured.length > 0 ? (
          <div className="grid gap-5 lg:grid-cols-2">
            {secured.map((s) => (
              <StrategyCard key={s.id} strategy={s} meta={metaById.get(s.id)} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-ink-muted">No secured strategies yet.</p>
        )}
      </section>
    </div>
  );
}
