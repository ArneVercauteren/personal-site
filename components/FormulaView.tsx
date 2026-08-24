import type { ReactNode } from "react";
import type { FormulaNode, StrategyFormula } from "@/lib/data";

// ---------------------------------------------------------------------------
// FormulaView — renders a scrubbed Astralanx DSL score tree as a readable, math-
// like expression. Pure presentation (server component): walks the tree the
// same way the vendored evaluator does (paper_trading/darwin_eval), but emits
// styled spans instead of numbers. The operator/indicator/transform tables and
// the prose below are kept faithful to that evaluator so the page describes
// exactly what the engine computes.
// See docs/subsystems/live-dashboard.md and lib/data.ts (FormulaNode).
// ---------------------------------------------------------------------------

// Infix symbols for the binary arithmetic operators the engine dispatches
// (paper_trading/darwin_eval/tree_eval.py::ARITHMETIC_OPS). Operators that read
// better as functions or brackets (min/max/mean/median/gates/log_ratio/…) are
// handled specially in `render`, not here.
const ARITHMETIC_OP: Record<string, string> = {
  add: "+",
  subtract: "−",
  multiply: "×",
  divide: "÷",
};

// Functional-form arithmetic ops: rendered as name(a, b, …).
const ARITHMETIC_FUNC: Record<string, string> = {
  minimum: "min",
  maximum: "max",
  mean: "mean",
  median: "median",
  soft_clip: "softclip",
  atan2: "atan2",
};

const COMPARISON_OP: Record<string, string> = {
  greater_than: ">",
  less_than: "<",
  greater_or_equal: "≥",
  less_or_equal: "≤",
  equal: "≈",
  almost_equal: "≈",
  not_equal: "≠",
};

const LOGIC_OP: Record<string, string> = {
  and: "AND",
  or: "OR",
  not: "NOT",
  nand: "NAND",
  nor: "NOR",
  implies: "⇒",
};

// Human labels + one-line descriptions for the indicators the evaluator can
// compute (paper_trading/darwin_eval/select_on_date.py). Anything not listed
// falls back to a humanized name. Every indicator is point-in-time: it is
// computed through the *prior* trading day's bar (the evaluator shifts each
// series by one day), so a rebalance never sees the day it trades on.
const INDICATOR_INFO: Record<string, { label: string; desc: string }> = {
  sma: { label: "SMA", desc: "Simple moving average of adjusted close over the window." },
  ema: { label: "EMA", desc: "Exponential moving average of adjusted close (span = window)." },
  roc: { label: "ROC", desc: "Rate of change — percent price move over the window." },
  rsi: { label: "RSI", desc: "Relative strength index (0–100) — overbought / oversold over the window." },
  atr: { label: "ATR", desc: "Average true range — typical daily price swing over the window." },
  beta: { label: "Beta", desc: "Rolling sensitivity of returns to the market proxy (needs a benchmark)." },
  mkt_corr: { label: "Market corr.", desc: "Rolling correlation of returns with the market proxy." },
  rvol: { label: "Realized vol", desc: "Standard deviation of daily returns over the window." },
  hh: { label: "Highest high", desc: "Highest high over the window." },
  ll: { label: "Lowest low", desc: "Lowest low over the window." },
  highest_high: { label: "Highest high", desc: "Highest high over the window." },
  lowest_low: { label: "Lowest low", desc: "Lowest low over the window." },
  dollar_volume: { label: "Dollar volume", desc: "Adjusted close × share volume — a liquidity measure." },
  volume_surge: { label: "Volume surge", desc: "Volume relative to its window average, minus one." },
  overnight_gap: { label: "Overnight gap", desc: "Open versus the prior close, as a fraction." },
  close_to_range: { label: "Close-in-range", desc: "Where the close sits within the day's high–low range (0–1)." },
  mean_reversion: { label: "Mean reversion", desc: "Price relative to its window moving average, minus one." },
  drawdown: { label: "Drawdown", desc: "Price relative to its window-high peak, minus one (≤ 0)." },
  skewness: { label: "Skewness", desc: "Skew of the daily-return distribution over the window." },
  amihud_illiquidity: { label: "Illiquidity", desc: "Amihud measure — mean |return| per dollar traded over the window." },
  // Path-dependent portfolio-state features the engine injects at each rebalance.
  current_portfolio_drawdown: { label: "Portfolio drawdown", desc: "The whole portfolio's current drawdown from its equity peak." },
  current_holdings_count: { label: "Holdings count", desc: "How many names the portfolio currently holds." },
  invested_fraction: { label: "Invested fraction", desc: "Share of the portfolio currently in positions (vs cash)." },
  cash_fraction: { label: "Cash fraction", desc: "Share of the portfolio currently in cash." },
};

// Labels + descriptions for the transforms the evaluator computes
// (paper_trading/darwin_eval/select_on_date.py::_compute_transformed_feature).
// `window` / `periods` / `n_bins` renders as a subscript on the pill.
const TRANSFORM_INFO: Record<string, { label: string; desc: string }> = {
  rank: {
    label: "rank",
    desc: "Cross-sectional percentile rank (0–1) of the feature's window-day average, across all eligible names that day.",
  },
  z_score: {
    label: "z‑score",
    desc: "Time-series z-score: (value − window mean) ÷ window std — standardised against its own recent history.",
  },
  quantile_bin: {
    label: "qbin",
    desc: "Cross-sectional rank bucketed into n_bins equal groups, rescaled to 0–1.",
  },
  lag: { label: "lag", desc: "The value as of `periods` trading days earlier." },
  diff: { label: "diff", desc: "Change in the value over `periods` trading days." },
  log: { label: "log", desc: "Signed log compression: sign(x) · ln(1 + |x|)." },
};

const TRANSFORM_LABEL: Record<string, string> = Object.fromEntries(
  Object.entries(TRANSFORM_INFO).map(([k, v]) => [k, v.label]),
);

function humanize(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function indicatorLabel(name: string): string {
  return INDICATOR_INFO[name]?.label ?? humanize(name);
}

// The most relevant numeric param to show as a node's subscript.
function subscriptParam(params?: Record<string, number | string>): string | null {
  if (!params) return null;
  const v = params.window ?? params.periods ?? params.n_bins;
  return v == null ? null : String(v);
}

// Round a literal to ~3 significant figures so the math stays legible.
function fmtNumber(v: number): string {
  if (v === 0) return "0";
  if (Number.isInteger(v)) return String(v);
  const rounded = Number(v.toPrecision(3));
  return String(rounded);
}

function Paren({ children }: { children: ReactNode }) {
  return (
    <>
      <span className="text-ink-muted/60">(</span>
      {children}
      <span className="text-ink-muted/60">)</span>
    </>
  );
}

function Op({ children }: { children: ReactNode }) {
  return <span className="mx-1.5 text-ink-muted">{children}</span>;
}

// A functional call: name(a, b, …).
function FuncCall({ name, kids }: { name: string; kids: (FormulaNode | undefined)[] }) {
  return (
    <span className="inline">
      <span className="text-ink">{name}</span>
      <Paren>
        {kids.map((k, i) => (
          <span key={i}>
            {i > 0 ? <span className="text-ink-muted">, </span> : null}
            {render(k)}
          </span>
        ))}
      </Paren>
    </span>
  );
}

// An Iverson bracket — a 1/0 gate. Used for the comparison nodes, which the
// engine evaluates to exactly 1.0 (true) or 0.0 (false).
function Gate({ children }: { children: ReactNode }) {
  return (
    <span className="inline">
      <span className="text-ink-muted">[</span>
      {children}
      <span className="text-ink-muted">]</span>
    </span>
  );
}

// Render an indicator leaf as a colored pill with an optional window subscript.
function Indicator({ node }: { node: FormulaNode }) {
  const name = node.name ?? "?";
  const sub = subscriptParam(node.params);
  const info = INDICATOR_INFO[name];
  return (
    <span
      className="inline-flex items-baseline rounded bg-accent/10 px-1.5 py-0.5 text-accent ring-1 ring-inset ring-accent/20"
      title={info ? info.desc : humanize(name)}
    >
      {indicatorLabel(name)}
      {sub ? <sub className="ml-0.5 text-[0.7em] text-accent/70">{sub}</sub> : null}
    </span>
  );
}

// Render one node recursively. `paren` requests wrapping in parentheses when the
// node is a composite operand of a larger expression.
function render(node: FormulaNode | undefined, paren = false): ReactNode {
  if (!node) return null;

  switch (node.kind) {
    case "number":
      return <span className="text-ink-muted">{fmtNumber(node.value ?? 0)}</span>;

    case "indicator":
      return <Indicator node={node} />;

    case "transform": {
      const label = TRANSFORM_LABEL[node.name ?? ""] ?? humanize(node.name ?? "f");
      const sub = subscriptParam(node.params);
      const info = TRANSFORM_INFO[node.name ?? ""];
      return (
        <span className="inline-flex items-baseline">
          <span className="text-ink" title={info?.desc}>
            {label}
          </span>
          {sub ? <sub className="text-[0.7em] text-ink-muted">{sub}</sub> : null}
          <span className="ml-0.5">
            <Paren>{render(node.child)}</Paren>
          </span>
        </span>
      );
    }

    case "arithmetic": {
      const kids = node.children ?? [];
      const name = node.name ?? "";

      // |a − b| reads better than abs_diff(a, b).
      if (name === "abs_diff" && kids.length === 2) {
        return (
          <span className="inline">
            <span className="text-ink-muted/60">|</span>
            {render(kids[0], true)}
            <Op>−</Op>
            {render(kids[1], true)}
            <span className="text-ink-muted/60">|</span>
          </span>
        );
      }

      // ln(a ÷ b) for the log_ratio operator.
      if (name === "log_ratio" && kids.length >= 2) {
        return (
          <span className="inline">
            <span className="text-ink">ln</span>
            <Paren>
              {render(kids[0], true)}
              <Op>÷</Op>
              {render(kids[1], true)}
            </Paren>
          </span>
        );
      }

      // 1/0 gates: gate_pos(a,b) = [a > b]; gate_neg(a,b) = [a < b].
      if ((name === "gate_pos" || name === "gate_neg") && kids.length >= 2) {
        return (
          <Gate>
            {render(kids[0], true)}
            <Op>{name === "gate_pos" ? ">" : "<"}</Op>
            {render(kids[1], true)}
          </Gate>
        );
      }

      // Functional form (min, max, mean, median, softclip, atan2).
      const fn = ARITHMETIC_FUNC[name];
      if (fn) return <FuncCall name={fn} kids={kids} />;

      // Infix for +, −, ×, ÷ (and any unmapped n-ary op, by name).
      const sym = ARITHMETIC_OP[name] ?? name;
      const body = (
        <span>
          {kids.map((k, i) => (
            <span key={i}>
              {i > 0 ? <Op>{sym}</Op> : null}
              {render(k, true)}
            </span>
          ))}
        </span>
      );
      return paren ? <Paren>{body}</Paren> : body;
    }

    case "comparison": {
      const name = node.name ?? "";

      // Unary sign tests render as [a ⋈ 0].
      const unary: Record<string, string> = {
        is_positive: "> 0",
        is_negative: "< 0",
        is_nonzero: "≠ 0",
      };
      if (unary[name]) {
        return (
          <Gate>
            {render(node.left, true)}
            <Op>{unary[name]}</Op>
          </Gate>
        );
      }

      // Sign-relation tests.
      if (name === "same_sign" || name === "different_sign") {
        return (
          <FuncCall
            name={name === "same_sign" ? "same-sign" : "opp-sign"}
            kids={[node.left, node.right]}
          />
        );
      }

      // Ternary band tests: between → [b ≤ a ≤ c]; in_band → [|a − b| < c].
      if (name === "between" && node.third) {
        return (
          <Gate>
            {render(node.right, true)}
            <Op>≤</Op>
            {render(node.left, true)}
            <Op>≤</Op>
            {render(node.third, true)}
          </Gate>
        );
      }
      if ((name === "outside" || name === "in_band") && node.third) {
        return <FuncCall name={humanize(name)} kids={[node.left, node.right, node.third]} />;
      }
      if (name === "greater_abs" || name === "less_abs") {
        return (
          <Gate>
            <span className="text-ink-muted/60">|</span>
            {render(node.left, true)}
            <span className="text-ink-muted/60">|</span>
            <Op>{name === "greater_abs" ? ">" : "<"}</Op>
            <span className="text-ink-muted/60">|</span>
            {render(node.right, true)}
            <span className="text-ink-muted/60">|</span>
          </Gate>
        );
      }

      const sym = COMPARISON_OP[name] ?? name;
      return (
        <Gate>
          {render(node.left, true)}
          <Op>{sym}</Op>
          {render(node.right, true)}
        </Gate>
      );
    }

    case "logic": {
      const name = node.name ?? "";
      const kids = node.children ?? node.clauses ?? [];

      if (name === "not") {
        return (
          <span>
            <span className="mr-1 text-ink-muted">NOT</span>
            {render(kids[0], true)}
          </span>
        );
      }
      // if_bool(cond, a, b): pick a when the condition holds, else b.
      if (name === "if_bool" && kids.length >= 3) {
        return (
          <span className="inline">
            <span className="text-ink-muted">if</span> {render(kids[0], true)}{" "}
            <span className="text-ink-muted">then</span> {render(kids[1])}{" "}
            <span className="text-ink-muted">else</span> {render(kids[2])}
          </span>
        );
      }

      const sym = LOGIC_OP[name] ?? name.toUpperCase();
      const body = (
        <span>
          {kids.map((k, i) => (
            <span key={i}>
              {i > 0 ? <Op>{sym}</Op> : null}
              {render(k, true)}
            </span>
          ))}
        </span>
      );
      return paren ? <Paren>{body}</Paren> : body;
    }

    case "conditional": {
      const cases = node.cases ?? [];
      return (
        <span>
          {cases.map((c, i) => (
            <span key={i}>
              {c.condition ? (
                <>
                  <span className="text-ink-muted">if</span> {render(c.condition, true)}{" "}
                  <span className="text-ink-muted">then</span> {render(c.result)}{" "}
                </>
              ) : (
                <>
                  <span className="text-ink-muted">else</span> {render(c.else ?? c.result)}
                </>
              )}
            </span>
          ))}
        </span>
      );
    }

    default:
      return null;
  }
}

// Collect the distinct indicators referenced anywhere in the tree, for the glossary.
function collectIndicators(node: FormulaNode | undefined, into: Set<string>): void {
  if (!node) return;
  if (node.kind === "indicator" && node.name) into.add(node.name);
  for (const child of [node.child, node.left, node.right, node.third]) {
    collectIndicators(child, into);
  }
  for (const child of node.children ?? []) collectIndicators(child, into);
  for (const child of node.clauses ?? []) collectIndicators(child, into);
  for (const c of node.cases ?? []) {
    collectIndicators(c.condition, into);
    collectIndicators(c.result, into);
    collectIndicators(c.else, into);
  }
}

// Collect the distinct transforms referenced anywhere in the tree, for the glossary.
function collectTransforms(node: FormulaNode | undefined, into: Set<string>): void {
  if (!node) return;
  if (node.kind === "transform" && node.name) into.add(node.name);
  for (const child of [node.child, node.left, node.right, node.third]) {
    collectTransforms(child, into);
  }
  for (const child of node.children ?? []) collectTransforms(child, into);
  for (const child of node.clauses ?? []) collectTransforms(child, into);
  for (const c of node.cases ?? []) {
    collectTransforms(c.condition, into);
    collectTransforms(c.result, into);
    collectTransforms(c.else, into);
  }
}

function intervalLabel(interval?: string): string | null {
  if (!interval) return null;
  const m = /^(\d+)\s*([dwmy])$/i.exec(interval.trim());
  if (!m) return interval;
  const n = Number(m[1]);
  const unit = { d: "day", w: "week", m: "month", y: "year" }[m[2].toLowerCase()] ?? "";
  return `${n} ${unit}${n === 1 ? "" : "s"}`;
}

function topLevelScorePieces(formula: StrategyFormula): FormulaNode[] {
  if (
    formula.kind === "arithmetic" &&
    formula.children &&
    formula.children.length > 1
  ) {
    return formula.children;
  }
  return [formula];
}

function opLabel(node: FormulaNode): string {
  if (node.kind === "number") return "Constant";
  if (node.kind === "indicator") return indicatorLabel(node.name ?? "indicator");
  if (node.kind === "transform") {
    const base = TRANSFORM_LABEL[node.name ?? ""] ?? humanize(node.name ?? "transform");
    const sub = subscriptParam(node.params);
    return sub ? `${base} ${sub}` : base;
  }
  if (node.kind === "arithmetic") {
    const name = node.name ?? "score";
    if (name === "add") return "Add terms";
    if (name === "subtract") return "Subtract";
    if (name === "multiply") return "Multiply terms";
    if (name === "divide") return "Divide";
    if (name === "abs_diff") return "Absolute difference";
    if (name === "log_ratio") return "Log ratio";
    if (name === "gate_pos") return "Positive gate";
    if (name === "gate_neg") return "Negative gate";
    return ARITHMETIC_FUNC[name] ?? humanize(name);
  }
  if (node.kind === "comparison") return `Gate: ${humanize(node.name ?? "comparison")}`;
  if (node.kind === "logic") return `Logic: ${humanize(node.name ?? "logic")}`;
  if (node.kind === "conditional") return "Conditional";
  return humanize(node.kind);
}

function nodeNote(node: FormulaNode): string | null {
  if (node.kind === "indicator" && node.name) {
    return INDICATOR_INFO[node.name]?.desc ?? null;
  }
  if (node.kind === "transform" && node.name) {
    return TRANSFORM_INFO[node.name]?.desc ?? null;
  }
  if (node.kind === "arithmetic") {
    if (node.name === "multiply") return "Both sides matter: if either side is small, this term shrinks.";
    if (node.name === "add") return "Adds these ingredients into one score contribution.";
    if (node.name === "abs_diff") return "Rewards distance between the two inputs, regardless of direction.";
    if (node.name === "divide") return "Scales the left input by the right input.";
  }
  if (node.kind === "comparison" || node.kind === "logic") {
    return "Outputs a 1 / 0 switch used to include, exclude, or scale part of the score.";
  }
  return null;
}

function childNodes(node: FormulaNode): { label: string; node: FormulaNode }[] {
  if (node.kind === "transform" && node.child) {
    return [{ label: "Input", node: node.child }];
  }
  if (node.kind === "arithmetic" && node.children) {
    return node.children.map((child, i) => ({ label: `Input ${i + 1}`, node: child }));
  }
  if (node.kind === "logic") {
    const kids = node.children ?? node.clauses ?? [];
    return kids.map((child, i) => ({ label: `Clause ${i + 1}`, node: child }));
  }
  if (node.kind === "comparison") {
    return [
      node.left ? { label: "Left", node: node.left } : null,
      node.right ? { label: "Right", node: node.right } : null,
      node.third ? { label: "Band", node: node.third } : null,
    ].filter((v): v is { label: string; node: FormulaNode } => v !== null);
  }
  if (node.kind === "conditional") {
    return (node.cases ?? []).flatMap((c, i) =>
      [
        c.condition ? { label: `Case ${i + 1} condition`, node: c.condition } : null,
        c.result ? { label: `Case ${i + 1} result`, node: c.result } : null,
        c.else ? { label: `Case ${i + 1} else`, node: c.else } : null,
      ].filter((v): v is { label: string; node: FormulaNode } => v !== null),
    );
  }
  return [];
}

function FormulaTree({
  node,
  label = "Score",
  depth = 0,
}: {
  node: FormulaNode;
  label?: string;
  depth?: number;
}) {
  const children = childNodes(node);
  const note = nodeNote(node);

  return (
    <div className={depth === 0 ? "rounded border border-hair bg-panel p-4" : "border-l border-hair pl-3"}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
          {label}
        </p>
        <p className="text-xs text-ink-muted">{kindSummary(node)}</p>
      </div>
      <h5 className="mt-1 text-sm font-semibold text-ink">{opLabel(node)}</h5>
      {note ? <p className="mt-1 text-xs text-ink-muted">{note}</p> : null}
      <div className="mt-2 whitespace-normal break-words font-mono text-sm leading-7 text-ink">
        {render(node)}
      </div>
      {children.length > 0 ? (
        <div className="mt-3 flex flex-col gap-3">
          {children.map((child, i) => (
            <FormulaTree
              key={`${depth}-${i}-${child.label}`}
              node={child.node}
              label={child.label}
              depth={depth + 1}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function kindSummary(node: FormulaNode): string {
  if (node.kind === "indicator") {
    return indicatorLabel(node.name ?? "indicator");
  }
  if (node.kind === "transform") {
    const label = TRANSFORM_LABEL[node.name ?? ""] ?? humanize(node.name ?? "transform");
    return `${label} transform`;
  }
  if (node.kind === "comparison") return "1 / 0 gate";
  if (node.kind === "logic") return "logic gate";
  if (node.kind === "conditional") return "conditional branch";
  if (node.kind === "arithmetic") {
    const name = node.name ?? "score";
    if (name === "multiply") return "weighted or gated term";
    if (name === "add") return "score sum";
    if (name === "mean") return "average score";
    return humanize(name);
  }
  return humanize(node.kind);
}

function SummaryCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="border border-hair bg-panel px-4 py-3">
      <dt className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
        {label}
      </dt>
      <dd className="mt-1 text-sm font-semibold text-ink">{value}</dd>
      <dd className="mt-1 text-xs text-ink-muted">{note}</dd>
    </div>
  );
}

export function FormulaView({
  formula,
  rebalanceDays,
}: {
  formula: StrategyFormula;
  rebalanceDays?: number;
}) {
  const indicators = new Set<string>();
  collectIndicators(formula, indicators);
  collectIndicators(formula.exit_root, indicators);
  const glossary = [...indicators].sort();

  const transforms = new Set<string>();
  collectTransforms(formula, transforms);
  collectTransforms(formula.exit_root, transforms);
  const transformGlossary = [...transforms].sort();

  const interval = intervalLabel(formula.rebalance_interval);
  const cadence =
    interval ?? (rebalanceDays ? `${rebalanceDays} trading days` : null);
  const selectionValue = formula.top_n ? `Top ${formula.top_n}` : "Top ranked";

  return (
    <div className="flex flex-col gap-6">
      <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-hair bg-hair sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          label="Selection"
          value={selectionValue}
          note="Names are sorted by score; highest scores enter the basket."
        />
        <SummaryCard
          label="Cadence"
          value={cadence ?? "Strategy default"}
          note="The formula is re-evaluated on each rebalance date."
        />
        <SummaryCard
          label="Inputs"
          value={`${glossary.length} indicators`}
          note={`${transformGlossary.length} transforms shape those raw inputs.`}
        />
        <SummaryCard
          label="Exit"
          value={formula.exit_root ? "Has rule" : "Score only"}
          note={
            formula.exit_root
              ? "A separate gate can force stale holdings out."
              : "Holdings leave only when they fall out of the top ranks."
          }
        />
      </dl>

      <p className="max-w-prose text-sm text-ink-muted">
        Each rebalance, every <strong className="text-ink">eligible</strong> stock is
        scored by the expression below.
        {formula.top_n ? (
          <>
            {" "}
            The <strong className="text-ink">top {formula.top_n}</strong> highest-scoring
            names are held, weighted by rank (higher score → larger weight, each capped)
          </>
        ) : (
          " The highest-scoring names are held"
        )}
        {cadence ? <>, refreshed about every {cadence}.</> : "."} The exact formula is
        published verbatim — nothing is hidden for open strategies.
      </p>

      <ul className="max-w-prose list-disc space-y-1 pl-5 text-sm text-ink-muted">
        <li>
          <strong className="text-ink">Point-in-time.</strong> Every indicator is computed
          through the <em>prior</em> trading day, so a rebalance never peeks at the bar it
          trades on, preventing look-ahead.
        </li>
        <li>
          <strong className="text-ink">Cross-sectional vs. time-series.</strong>{" "}
          <code className="text-ink">rank</code> 
           compares a name against every other <em>eligible</em> name that day;{" "}
          <code className="text-ink">z‑score</code> standardises a value against its own
          recent history.
        </li>
        <li>
          <strong className="text-ink">Eligible</strong> means a raw price ≥ $10, trailing
          median dollar volume ≥ $5M, and recent, non-stale data — the same liquidity screen
          the backtest used.
        </li>
        <li>
          <strong className="text-ink">Comparisons and logic</strong> act as 1 / 0 gates
          (shown in <span className="text-ink-muted">[ ]</span> brackets) that switch parts
          of the score on or off. The score&apos;s absolute value is meaningless; only the
          ordering across names selects the basket.
        </li>
      </ul>

      <div>
        <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
          Full expression
        </h4>
        <div className="panel whitespace-normal break-words p-4 font-mono text-sm leading-8 text-ink sm:text-[0.95rem]">
          {render(formula)}
        </div>
      </div>

      {formula.exit_root ? (
        <div>
          <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
            Exit rule
          </h4>
          <p className="mb-2 max-w-prose text-sm text-ink-muted">
            Independently of the score, this gate can force a current holding out.
            If the score still ranks that name back into the target basket, the score wins.
          </p>
          <div className="panel whitespace-normal break-words p-4 font-mono text-sm leading-8 text-ink sm:text-[0.95rem]">
            {render(formula.exit_root)}
          </div>
        </div>
      ) : null}

      {glossary.length > 0 ? (
        <div>
          <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
            Indicators used
          </h4>
          <dl className="grid grid-cols-1 gap-x-8 gap-y-2 sm:grid-cols-2">
            {glossary.map((name) => {
              const info = INDICATOR_INFO[name];
              return (
                <div key={name} className="flex flex-col">
                  <dt className="text-sm font-medium text-ink">{indicatorLabel(name)}</dt>
                  <dd className="text-sm text-ink-muted">
                    {info ? info.desc : humanize(name)}
                  </dd>
                </div>
              );
            })}
          </dl>
        </div>
      ) : null}

      {transformGlossary.length > 0 ? (
        <div>
          <h4 className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-muted">
            Transforms used
          </h4>
          <dl className="grid grid-cols-1 gap-x-8 gap-y-2 sm:grid-cols-2">
            {transformGlossary.map((name) => {
              const info = TRANSFORM_INFO[name];
              return (
                <div key={name} className="flex flex-col">
                  <dt className="text-sm font-medium text-ink">
                    {info?.label ?? humanize(name)}
                  </dt>
                  <dd className="text-sm text-ink-muted">{info?.desc ?? humanize(name)}</dd>
                </div>
              );
            })}
          </dl>
        </div>
      ) : null}
    </div>
  );
}
