import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/PageHeader";

export const metadata: Metadata = {
  title: "Astralanx",
  description:
    "How Astralanx works: the Tiingo price data, the investable universe and filters, the backtesting model, the cost model, and out-of-sample testing",
};

function Section({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="mt-12 border-t border-hair pt-10">
      <p className="mb-2 font-mono text-xs uppercase tracking-widest text-accent">
        {eyebrow}
      </p>
      <h2 className="text-2xl font-semibold tracking-tight text-ink">{title}</h2>
      <div className="mt-4 max-w-prose space-y-4 leading-relaxed text-ink-muted">
        {children}
      </div>
    </section>
  );
}

function Bullets({ children }: { children: ReactNode }) {
  return (
    <ul className="list-disc space-y-2 pl-5 marker:text-hair">{children}</ul>
  );
}

// Headline scale figures, gathered from the Darwin source tree. Honest,
// de-duplicated counts: src/ Python (67,507 lines), the native_eval.c +
// generator_native.c + ffill_fast.c kernels (12,522 lines), and the
// post-filter tradable universe (~3,500 names after the ≥$10 / ≥$5M median
// dollar-volume screens; the raw listing file is far larger).
const stats: { value: string; label: string }[] = [
  { value: "65K+", label: "lines of Python" },
  { value: "~12K", label: "lines of native C" },
  { value: "~3,500", label: "names in the tradable universe" },
];

function StatStrip() {
  return (
    <dl className="mt-10 grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-hair bg-hair sm:grid-cols-3">
      {stats.map((s) => (
        <div key={s.label} className="bg-panel px-5 py-5">
          <dt className="font-mono text-2xl font-semibold tabular-nums text-accent">
            {s.value}
          </dt>
          <dd className="mt-1 text-sm text-ink-muted">{s.label}</dd>
        </div>
      ))}
    </dl>
  );
}

function C({ children }: { children: ReactNode }) {
  return (
    <code className="rounded bg-elevated px-1.5 py-0.5 font-mono text-[0.85em] text-ink">
      {children}
    </code>
  );
}

export default function AstralanxPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Project"
        title="Astralanx"
        intro="Astralanx is a system built to discover long-term quantitative stock-picking strategies and then run the best of them as a simulated portfolio. This page describes the methodology: where the data is imported from, how a candidate strategy is backtested, how realistic costs are simulated, the filters used to define a realistic investable universe, and how out-of-sample testing is applied."
      />

      <StatStrip />

      {/* The most prominent action: go see the strategies. */}
      <div className="mt-10 flex flex-wrap items-center gap-4">
        <Link
          href="/astralanx/live"
          className="inline-flex items-center gap-2 rounded-lg bg-accent px-6 py-3 text-base font-semibold text-[#0a0c10] shadow-sm transition-transform hover:-translate-y-0.5"
        >
          View the strategies
          <span aria-hidden>→</span>
        </Link>
        <span className="text-sm text-ink-muted">
          Live performance for every deployed strategy, with additional open-formula
          strategies broken out on their own.
        </span>
      </div>

      <Section eyebrow="The engine" title="A genetic-programming search">
        <p>
          Astralanx is a highly performant genetic-programming engine.
          It generates large populations of candidate strategies, evaluates each
          one against historical market data, and evolves them across
          many generations.
        </p>
        <p>
          How those strategies are represented and evolved is intentionally kept
          private. What is documented here is everything that accompanies the GP algorithm (data, the backtesting system, cost simulation model, and
          validation/safety measures). 
        </p>
      </Section>

      <Section eyebrow="Data source" title="Tiingo price data, and nothing else">
        <p>
          Every strategy is purely price-based and cross-sectional. There are no
          fundamentals, no macro inputs, no alternative data, and no
          discretionary overrides — all signal is derived from each ticker&apos;s
          own price and volume history, plus a single benchmark series.
        </p>
        <Bullets>
          <li>
            Per-ticker market data comes from{" "}
            <a
              href="https://www.tiingo.com"
              className="text-accent hover:underline"
              target="_blank"
              rel="noreferrer"
            >
              Tiingo
            </a>
            : <C>adj_close</C>, <C>adj_open</C>, <C>adj_high</C>, <C>adj_low</C>,{" "}
            <C>adj_volume</C>, and the unadjusted <C>close</C>.
          </li>
          <li>
            The adjusted OHLCV fields drive every signal and ranking feature. The
            unadjusted close is used only for the minimum-price eligibility gate,
            specifically so a stock split cannot leak future information into a
            historical decision.
          </li>
          <li>
            The benchmark is the S&amp;P 500 series, used for benchmark-relative
            and market-relative measurements.
          </li>
        </Bullets>
        <p>
          The starting universe is built from Tiingo listing metadata for the
          NYSE, NASDAQ, AMEX, NYSE MKT, NYSE ARCA, and BATS exchanges. Forex,
          crypto, and mutual-fund entries are dropped at build time, along with
          obvious non-common share classes. It is important to note that this selection of exchanges is likely quite arbitrary, given their universe scale these strategies will likely work with any large stock-based universe.
        </p>
      </Section>

      <Section
        eyebrow="Universe & filters"
        title="What is allowed into the backtest"
      >
        <p>
          The selectable universe is then narrowed by two kinds of filters:
          filters that remove obviously malformed or partially missing data, and
          filters that remove niche, risky, or structurally unconventional
          tickers. It&apos;s worth knowing that the second category largely
          subsumes the first — for the
          conventional names these strategies trade, Tiingo&apos;s data is very
          reliable.
        </p>
        <Bullets>
          <li>
            Tickers flagged with extreme or malformed prices are excluded under a
            strict default setting.
          </li>
          <li>
            Non-common instruments — warrants, units, rights, preferreds, and
            structurally non-tradable symbols — are removed, as are FX, crypto,
            mutual-fund, and OTC-style entries.
          </li>
          <li>
            Any ticker whose adjusted-close max/min span is at least 100,000&times;
            over its history, or that prints an absolute one-day return of 10,000%
            or more, is thrown out as corrupt.
          </li>
        </Bullets>
        <p>
          On top of the static universe, every date applies{" "}
          <strong>causal</strong> eligibility rules — using only information that
          existed on that date:
        </p>
        <Bullets>
          <li>
            The ticker must already have begun trading, and must not be past its
            last real observation.
          </li>
          <li>
            It must not be in a stale-data gap. Once a price has been
            forward-filled for more than seven trading days the name is marked
            stale and excluded from new selection.
          </li>
          <li>
            Its unadjusted close on the rebalance date must be at least $10.
          </li>
          <li>
            It must clear a 63-day trailing median dollar-volume screen of at
            least $5M, shifted by a day so the screen is
            never computed on the day it acts.
          </li>
        </Bullets>
        <p>
          Survivorship bias is handled the hard way. There is no
          present-day-survivors universe: a name becomes eligible only once it
          has actually begun trading in the historical record, and it leaves the
          universe once it is past its last real observation. When a name goes
          stale or delists, the engine applies a one-time 100% penalty to the
          transition and then zeroes its returns — so a position that quietly
          disappears from the data is forced to take a realistic exit hit rather
          than coasting at its last good mark.
        </p>
      </Section>

      <Section eyebrow="Backtesting" title="The backtesting model">
        <p>
          The backtest is deliberately simple, so the results are easy to reason
          about and hard to game.
        </p>
        <Bullets>
          <li>
            <strong>Daily bars.</strong> Strategies are evaluated on daily price
            data — no intraday or tick assumptions.
          </li>
          <li>
            <strong>Signal on the rebalance date.</strong> On each rebalance the
            formula is evaluated against the data available <em>as of</em> that
            date to produce target weights. Between rebalances the basket is held
            fixed and marked to market.
          </li>
          <li>
            <strong>Next-open fills.</strong> When the basket changes, fills land
            at the <em>next</em> bar&apos;s open — never at the close that
            produced the signal. This removes the classic look-ahead bias of
            trading on a price you could not have acted on.
          </li>
          <li>
            <strong>Four regimes over twenty years.</strong> Training always
            spans four non-overlapping five-year regimes, this tests the strategy across a variety of market conditions and ensures it isn&apos;t just optimised for one particular stretch.
          </li>
        </Bullets>
        <p>
          The headline statistics mean what they usually mean:{" "}
          <strong>CAGR</strong> (compound annual growth rate),{" "}
          <strong>Sharpe</strong> (risk-adjusted return), and{" "}
          <strong>max drawdown</strong> (worst peak-to-trough decline).
        </p>
      </Section>

      <Section eyebrow="Costs" title="The cost model">
        <p>
          Ignoring trading costs overstates returns, so every fill is charged
          across several components rather than a flat fee. All of them are
          configurable; the defaults below are the ones behind the published
          numbers. (strategies can be rerun with different cost assumptions on request)
        </p>
        <Bullets>
          <li>
            <strong>Commission</strong> — a base of 5 bps on traded notional (1 bp
            = 0.01%).
          </li>
          <li>
            <strong>Slippage</strong> — a base of 5 bps per 1.0 of turnover, where
            turnover is the exact sum of absolute weight changes between the
            drifted prior holdings and the new targets.
          </li>
          <li>
            <strong>Volatility scaling.</strong> Both commission and slippage are
            scaled by{" "}
            <C>1 + 0.75 · √(realized_vol_63d / long_term_vol_252d)</C>, so trading
            into turbulent markets costs more.
          </li>
          <li>
            <strong>Price scaling.</strong> Slippage is further scaled by{" "}
            <C>50 / harmonic_mean_portfolio_price</C> — lower-priced baskets pay
            proportionally more.
          </li>
          <li>
            <strong>Market impact.</strong> A square-root impact term,{" "}
            <C>0.5 · √(trade_value / ADV)</C>, is applied weight by weight against
            each name&apos;s rebalance-date dollar volume. If average daily volume
            is missing, a punitive 5% impact charge is applied to that weight.
          </li>
        </Bullets>
        <p>
          The exact
          commission and slippage used for each deployed strategy are published
          alongside it on the dashboard as well.
        </p>
      </Section>

      <Section
        eyebrow="Validation"
        title="Out-of-sample testing & validity measures"
      >
        <p>
          The single most important rule in the engine is the{" "}
          <strong>train / out-of-sample firewall</strong>. Fitness is computed on
          training data only. We reserve an out-of-sample test only for the most promising strategies
        </p>
        <p>
          Crucially, the out-of-sample test is run only rarely, on a handful of
          specific contenders. That rules out the obvious objection that strong
          out-of-sample numbers are just an artifact of testing thousands of
          variants against the holdout — which would basically amount to just using those years as extra training data.
        </p>
        <p>
          When a strategy is replayed on unseen data, several validity measures
          are computed to check that it is a real edge rather than a fragile
          curve fit:
        </p>
        <Bullets>
          <li>
            <strong>Directional consistency</strong> between the development
            period and the unseen window — CAGR, Sharpe, and drawdown should stay
            in the same ballpark, not collapse.
          </li>
          <li>
            <strong>Rolling-window stress</strong> — worst rolling 3- and 5-year
            CAGR, and rolling Sharpe, to see how bad a bad stretch actually gets.
          </li>
          <li>
            <strong>Benchmark relationship</strong> — correlation and beta against
            the S&amp;P 500, so the return stream isn&apos;t just leverage on the
            index.
          </li>
          <li>
            <strong>Factor decomposition</strong> — a Fama-French regression
            (market, size, value, profitability, investment, momentum, reversal)
            to measure annualized alpha and confirm the strategy isn&apos;t a
            repackaging of one standard style sleeve.
          </li>
          <li>
            <strong>Sector exposure & active share</strong> — how far the basket
            departs from an equal-weight eligible universe, reported as aggregate
            sector exposure.
          </li>
          <li>
            <strong>Capacity</strong> — two views: a liquidity-screening estimate
            (how large the book could get while staying a small fraction of each
            name&apos;s volume) and a stricter impact-consistent estimate using the
            same square-root impact model as the backtest that only allows 100bps slippage.
          </li>
        </Bullets>
        <p>
          Open strategies show all of this end to end, including the full basket.
          Secured live strategies publish performance and aggregate sector exposure
          only.
        </p>
      </Section>

      <div className="mt-12 rounded-lg border border-accent/30 bg-accent/5 p-5 text-sm text-ink-muted">
        Everything on the dashboard is a{" "}
        <span className="text-ink">simulated paper portfolio </span> 
         This is not <strong>investment advice</strong>.
      </div>

      <div className="mt-8">
        <Link
          href="/astralanx/live"
          className="inline-flex items-center gap-2 rounded-lg bg-accent px-6 py-3 text-base font-semibold text-[#0a0c10] shadow-sm transition-transform hover:-translate-y-0.5"
        >
          View the strategies
          <span aria-hidden>→</span>
        </Link>
      </div>
    </div>
  );
}
