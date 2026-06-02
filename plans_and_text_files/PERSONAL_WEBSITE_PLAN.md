# Personal Website & Live (Paper) Trading Plan

> Goal: a personal website hosting (a) a featured **Darwin** section with specific results, (b) a
> live **paper-trading** dashboard for selected Darwin strategies, (c) creative work (essays,
> music, art), and (d) a bio/résumé and general portfolio.
>
> Budget target: **~$10–20/yr** (domain only; everything else on free tiers).
> Trading: **paper / simulated only** — no broker, no real money, no order endpoints.

---

## 1. Guiding principles

1. **The public site is read-only.** It never executes trades and never holds API keys or
   broker credentials. It only *renders* data someone else computed.
2. **Three tiers, strictly separated** (see §2). The heavy Darwin engine stays on your
   machine and *pushes data outward*; it is never publicly reachable.
3. **Two classes of strategy** (see §6). **Open** strategies are fully public (formula +
   weights + performance) for advertisement. **Secured** strategies publish *performance and
   aggregate exposure only* — never the formula, never the individual ticker weights.
4. **Start as static as possible.** Pre-computed JSON committed/published over a live server
   until you actually need one. This is what keeps it at ~$10/yr.
5. **Separate repos, separate deployments.** Nothing in the website can import
   `src/config/secrets.py`. Secret formulas and weights live only in a **private** repo.
6. **Reuse the stack you already run.** Next.js 15 + React 19 + Tailwind (the Darwin UI is on
   React 18; Next 15's App Router + MDX pairing requires React 19, so the site is on 19).

---

## 2. Architecture (three tiers, with a secured sub-pipeline)

```
TIER 3 — Darwin engine (your PC, PRIVATE)
   • Runs evolution, picks king strategies.
   • Deploys a king ONCE: pushes its scrubbed formula into the PRIVATE updater repo.
   • Not involved in the recurring loop — rebalancing re-evaluates a FIXED formula.
        │  one-way push, only when (re)deploying a king
        ▼
TIER 2 — Paper-trading updaters (GitHub Actions, free)
   ├─ 2a SECURED updater  (PRIVATE repo)
   │     • Holds secret king formulas + computed weights.
   │     • cron #1 (every 1–2 months): formula → target ticker weights  (the "rebalance")
   │     • cron #2 (daily): mark to market → equity curve + stats        (the "paper-trade")
   │     • Aggregates weights → sector/asset-class exposure (drops tickers).
   │     • Pushes ONLY sanitized JSON (curve + stats + exposure) to the public repo.
   └─ 2b OPEN updater     (PUBLIC repo)
         • Runs open strategies from PUBLIC formulas.
         • Writes FULL JSON (curve + stats + positions) to public/data/.
        │  commits/pushes data/*.json
        ▼
TIER 1 — Public website (Next.js on Vercel, FREE)
   • Static content (bio, essays, music, art, Darwin writeup) via MDX/components.
   • Live dashboard reads public/data/*.json:
       - Open    → badge "Open · formula shown", full positions table.
       - Secured → badge "Live paper · positions held private", curve + stats + exposure donut.
   • Auto-deploys on git push.
```

**Why a private repo for secured strategies:** the only truly sensitive assets are the
deployed king's DSL formula and the ticker weights it produces. The *evaluation engine* is
generic and can be public. So the secrets live in a private repo whose Actions do both the
rebalance and the daily mark automatically (no PC needed), and publish only a sanitized,
performance-plus-exposure snapshot. An equity curve is a 1-D projection of the weight vector
over time — it can't be inverted back to the weights, so performance is safe to show.

**Why this stays at ~$10/yr:** GitHub Actions is free (public and private, within generous
limits); Vercel/Cloudflare serve static JSON for free. The only paid item is the domain.

---

## 3. Tech choices (final, for the budget)

| Concern        | Choice                              | Cost        | Notes |
|----------------|-------------------------------------|-------------|-------|
| Domain         | Cloudflare Registrar (or Namecheap) | ~$10–15/yr  | At-cost, free DNS |
| DNS / TLS / CDN| Cloudflare (free plan)              | $0          | Free HTTPS, caching |
| Frontend       | Next.js 15 (App Router) + Tailwind  | $0          | Same as Darwin UI |
| Content        | MDX (Markdown + React components)   | $0          | Essays, project writeups |
| Charts         | Recharts                            | $0          | Equity curves, drawdown, exposure donut |
| Hosting        | **Vercel Hobby**                    | $0          | Push-to-deploy from GitHub |
| Data store     | Static JSON in repo (`/public/data`)| $0          | Tiny payloads; CDN-cached |
| Scheduled jobs | **GitHub Actions** (cron)           | $0          | Public + private updaters |
| Price data     | yfinance / stooq (keyless)          | $0          | Daily bars are plenty |
| Music embeds   | SoundCloud / Spotify / Bandcamp     | $0          | Or self-hosted audio in `public/` |
| Art            | Static images in `public/`          | $0          | Optimized via `next/image` |

**Total realistic spend: just the domain (~$12/yr).**

---

## 4. Site structure (information architecture)

Top-level nav, grouped to ~6 items (the "Studio hub" combines music + art):

```
Home  ·  About  ·  Darwin  ·  Live  ·  Writing  ·  Studio  ·  Projects
```

| Section | Route | Contents |
|---|---|---|
| **Home** | `/` | Hero (one-line identity), one featured Darwin result, links into each section |
| **About** | `/about` | Bio + résumé (web view + downloadable PDF) |
| **Darwin** | `/darwin` | The flagship section: what it is, how it works (DSL → compile → backtest → kings), the train/OOS firewall story, **specific results** (per-strategy result cards, regime breakdowns), a **Methodology** subsection with detailed explanations of the **backtesting model** and the **cost model** (see §6.5), link to Live |
| **Live** | `/darwin/live` | Paper-trading dashboard. Open strategies (full transparency) + secured strategies (curve + stats + aggregate exposure). Standing paper-only disclaimer |
| **Writing** | `/writing`, `/writing/[slug]` | Essays (MDX) |
| **Studio** | `/studio` | Music + Art hub. Music: embeds or self-hosted players. Art: image galleries with lightbox |
| **Projects** | `/projects`, `/projects/[slug]` | Other software / non-software portfolio (MDX writeups) |

Live can be a sub-route of Darwin (`/darwin/live`) while still appearing as its own nav item.

Full IA reference (routes, page responsibilities): `docs/reference/site-map.md`.

---

## 5. Theme — dark / technical throughout

A single cohesive **dark, quant-terminal** aesthetic across the whole site. Data-dense and
precise for Darwin/Live; the creative sections (music, art) use large media on the dark
canvas to carry warmth, so imagery — not chrome — provides the color.

Direction (concrete tokens live in `docs/reference/design-system.md`):

- **Surfaces:** near-black base (`#0a0c10`), panel (`#11151c`), elevated (`#161b22`).
- **Text:** `#e6edf3` primary, `#9da7b3` muted, on dark.
- **Signal accents:** terminal-green gains (`#3fb950`), red losses (`#f85149`), one cyan
  brand accent (`#39d0d8`) for links/highlights.
- **Type:** a clean sans for prose (Inter), a monospace for data/numbers/code (JetBrains Mono
  or IBM Plex Mono). Numbers in tables and charts are always mono and tabular-aligned.
- **Charts:** thin lines, faint grid, green/red P&L, minimal axes. Charts feel like a trading
  terminal, not a marketing dashboard.
- **Creative sections:** same dark frame, but media goes full-bleed/large; minimal UI so art
  and embeds dominate.

---

## 6. The two strategy classes

The dashboard renders two visibly distinct kinds of strategy. The distinction is a
**security boundary**, not just a UI label.

### Open strategies (1–2, for advertisement)

- **Formula:** published. Shown on the site (or linked from a writeup).
- **Weights:** published. Full positions table.
- **Where it runs:** the **public** repo's GitHub Actions (Tier 2b). Anyone can read the
  formula and reproduce the result — that auditability *is* the advertisement.
- **Published JSON:** `equity_curve`, `stats`, `positions`, `formula`/link.

### Secured strategies (the real kings)

- **Formula:** private. Never published, never in the public repo.
- **Weights:** private. Never published as individual tickers.
- **Disclosure:** **aggregate exposure only** — sector / asset-class allocation (e.g.
  "Technology 32%, Healthcare 18%"), plus the equity curve and headline stats. The breakdown is an
  **approximation** (SEC-derived sector map; unmapped names bucket into "Other"), and the live donut
  says so.
- **Where it runs:** a **private** repo's GitHub Actions (Tier 2a). It holds the formulas,
  does both the rebalance and the daily mark, maps tickers → sector and aggregates the
  weights, then pushes only the sanitized snapshot to the public repo.
- **Published JSON:** `equity_curve`, `stats`, `exposure` (grouped). **No** `positions`,
  **no** `formula`.

See `docs/concepts/open-vs-secured-strategies.md` and `docs/concepts/data-contract.md`.

### 6.4 Per-strategy metadata

Every deployed strategy (open or secured) carries a small block of **non-secret** descriptive
metadata, set when it's deployed and shown on the site. This is published in
`public/data/strategies.json`:

| Field | Example | Notes |
|---|---|---|
| `id` / `name` | `balanced_king_v3` / "Balanced King" | identity |
| `visibility` | `secured` | gates the data shape |
| `portfolio_size` | `100000` | the simulated capital this strategy runs on |
| `base_currency` | `USD` | |
| `rebalance_cadence_days` | `42` | how often it rebalances (≈ every 1–2 months) |
| `deployed_on` | `2026-05-01` | when it went live on the site |
| `cost_model` | `{commission_bps, slippage_bps, spread_ref_price, volume_impact_coef, impact_portfolio_size, vol_*}` | the full Darwin cost model (see §6.5); only the two bps fields are required, the rest default to Darwin's engine values |
| `blurb` | "Balanced risk/return king…" | one-line description |

None of this is sensitive — it describes *how the sim is run*, not the formula or the basket —
so it is published for both open and secured strategies.

### 6.5 Methodology content (the Darwin section)

The `/darwin` page carries a **Methodology** subsection that explains, in plain language:

- **The backtesting model** — daily bars; signal evaluated on the rebalance date; fills applied
  at the next bar's open; the train/OOS firewall (fitness clamped to the training cutoff, OOS
  used only for replay); non-overlapping regime windows; what CAGR / Sharpe / max-drawdown /
  Calmar mean here.
- **The cost model** — the **Darwin-faithful** model (`paper_trading/costs.py`): a per-rebalance
  equity haircut from turnover-scaled commission + **price-scaled slippage** (cheaper books pay
  more) + **sqrt volume impact** (sized against `impact_portfolio_size`, default Darwin's $1M) +
  a **crisis-aware volatility multiplier**. Same formulas as Darwin's `native_eval.c`, so the live
  paper curve carries the same costs the strategy was backtested under.

These are the *same* assumptions the live paper sim uses (§6.4 `cost_model`), so the
methodology page and the live numbers stay consistent. Authored as MDX under
`content/` (e.g. `content/essays/darwin-methodology.mdx` or a dedicated Darwin page block).

---

## 7. How the paper trading works (Tier 2)

A pure-Python simulator. No broker. Deterministic and re-runnable.

**The engine is not secret.** It lives in the public repo's `paper_trading/` package and can
be open source. Only the *deployed king formulas* and the *weights* are secret, and those
live solely in the private repo.

1. **Rebalance (every 1–2 months):** evaluate each deployed strategy's fixed formula against
   current data → target ticker weights (`signals.py`). For secured strategies this runs in
   the private repo; the weights are stored privately.
2. **Daily mark:** fetch latest daily bars (`prices.py`), mark the held weights to market,
   append today's equity point, recompute CAGR/Sharpe/maxDD (`portfolio.py`).
3. **Aggregate (secured only):** map tickers → sector/asset-class and sum weights → exposure.
   Drop the ticker-level detail.
4. **Write JSON:** open strategies → full JSON in the public repo; secured strategies →
   sanitized JSON pushed from the private repo to the public repo.
5. **Commit** → Vercel redeploys automatically.

**Signal evaluation parity:** **done via option B** — Darwin's DSL evaluator is vendored into
`paper_trading/darwin_eval/` (with an engine-faithful `portfolio_state.py`) and **parity-tested**
against Darwin's own `select_tickers_on_date` (`tests/test_evaluator_parity.py`). Selection + target
weights are bit-exact with Darwin; the evaluation *code* is public, the *formulas* are not. (The
lighter option A is no longer the path.)

### 7.1 Tradable universe (self-refreshing, Darwin-independent)

Each deployed strategy needs a *current* set of tickers to pick from each rebalance. Snapshotting
Darwin's universe at deploy time is **rejected**: it inherits Darwin's data age (a king deployed
off six-month-old data could never hold anything newer) and would pull a keyed paid feed +
Darwin's data into the public repo. Instead the universe is built in the public repo from public,
keyless sources and the **same filters Darwin uses**, and refreshes on its own schedule:

1. **Listings:** the **Nasdaq Trader symbol directory** (`nasdaqlisted.txt` + `otherlisted.txt`) —
   every NYSE/NASDAQ/AMEX symbol, updated each trading day, free + keyless (yfinance has no listing
   endpoint, so the symbol list comes from the exchanges' own files).
2. **Symbol filters:** drop test issues, warrants/units/rights/preferred, leveraged/inverse
   (regexes vendored from Darwin's `ticker_filtering.py`).
3. **Liquidity/price:** last close ≥ $10 and trailing median dollar volume ≥ $5M (Darwin's
   `FinancialRealism` thresholds), ranked by liquidity and capped (default top ~1,200) so daily
   fetches stay bounded. The evaluator's `eligibility.py` re-applies these at every rebalance.

A **monthly** workflow (`update_universe.py` → `universe-refresh.yml`) does the heavy fetch and
commits `public/data/universe.json`; the daily updater just reads it (`universe.resolve_universe`).
A strategy with an explicit non-empty `universe` keeps it; one that omits it resolves to the shared
file. So a king is deployed **once** and new tickers flow in via the monthly refresh — the Darwin
deploy stays decoupled from universe upkeep. See `docs/subsystems/universe.md`.

---

## 8. The secured pipeline (private repo) in detail

A separate **private** repository (e.g. `personal-site-trading`):

```
personal-site-trading/   (PRIVATE)
├─ strategies/            # secret king DSL formulas (optionally encrypted at rest)
├─ weights/              # computed target weights, committed privately
├─ ticker_sectors.json   # ticker → sector/asset-class map for aggregation
└─ .github/workflows/
   ├─ rebalance.yml       # cron (~monthly): formula → weights/*.json
   └─ daily.yml           # cron (daily): mark to market → sanitized snapshot → push to public
```

- The engine is reused from the public repo (git submodule or `pip install git+…`). The
  private repo adds only data (formulas, weights, sector map) and the two workflows.
- `daily.yml` pushes to the public repo via a deploy key / fine-grained PAT stored as an
  Actions secret. It copies **only** the sanitized `public/data/*.json` entries — never the
  contents of `strategies/` or `weights/`.
- **Optional hardening:** encrypt `strategies/*` at rest; decrypt in-runner with a key from an
  Actions secret. Darwin already has encryption tooling to borrow.

The public repo never receives, and its git history never contains, any formula or weight.

### 8.1 Deploying a strategy from Darwin (Tier 3)

Deployment is a one-shot operator action from the **Darwin UI**, now **built** as an export button:

- **The "Deploy to site" export (built).** Darwin's strategy drawer (`StrategyDrawer.tsx`) has two
  `ExportMenu` items — *Open strategy (public repo)* and *Secured strategy (private repo)* — backed
  by `GET /api/strategies/{id}/site-spec` (`ui/backend/exports/site.py`). It assembles the exact
  strategy-spec JSON the updater runs:
  1. **Formula** from the strategy's round-trippable `raw_json` (Darwin's `src/dsl/serialize.py`) —
     scrubbed, portable. Carried in **both** open and secured exports (the secured file lives in the
     private repo and is *run* there; the security boundary is enforced at publish via
     `assert_sanitized`, not by omitting the formula).
  2. **§6.4 metadata** + the full **`cost_model`** read live from the engine config (`cfg.realism`,
     `cfg.backtest_diag`; commission/slippage = Darwin's `5/5` CLI defaults).
  3. **`visibility`** chosen by which menu item; open also gets a public `formula_ref`.
  4. **`universe` left empty** → resolves to the shared self-refreshing universe (§7.1), so a king
     deployed once stays current. **Cadence:** `rebalance_cadence_days` + `next_rebalance_date` are
     stamped so the daily cron rebalances strategies when due.
- The operator drops the downloaded file into the public repo's `paper_trading/strategies/` (open) or
  the private repo's `strategies/` (secured). A future `scripts/deploy_to_site.py` can automate that
  placement; the button produces the correct file today.

This keeps Darwin's involvement to a single click per strategy; the recurring rebalance + daily mark
are fully automatic thereafter (§2). See `docs/subsystems/darwin-publish.md`.

---

## 9. Repository structure (public repo: `personal-site`)

```
personal-site/
├─ app/                                # Next.js App Router (Tier 1)
│  ├─ layout.tsx                       # nav, footer, dark theme
│  ├─ page.tsx                         # home
│  ├─ about/page.tsx                   # bio + résumé
│  ├─ darwin/
│  │  ├─ page.tsx                      # Darwin explainer + results
│  │  └─ live/page.tsx                # live dashboard
│  ├─ writing/{page.tsx,[slug]/page.tsx}
│  ├─ studio/page.tsx                  # music + art hub
│  └─ projects/{page.tsx,[slug]/page.tsx}
├─ content/
│  ├─ essays/*.mdx
│  └─ projects/*.mdx
├─ components/
│  ├─ Nav.tsx  Footer.tsx
│  ├─ EquityCurveChart.tsx  DrawdownChart.tsx  ExposureDonut.tsx
│  ├─ StatsTable.tsx  StrategyCard.tsx  Disclaimer.tsx
│  └─ studio/{MusicPlayer.tsx,ArtGallery.tsx}
├─ lib/
│  ├─ data.ts                          # THE DATA CONTRACT (typed loaders)
│  ├─ content.ts                       # MDX/frontmatter loading
│  └─ format.ts                        # %, $, date helpers
├─ paper_trading/                      # Tier-2 ENGINE (not secret; runs OPEN strategies here)
│  ├─ requirements.txt  update.py  prices.py  portfolio.py  signals.py
│  ├─ costs.py  secured.py             # Darwin cost model; secured sanitizer + leak guard
│  ├─ universe.py  update_universe.py  ticker_sectors.json   # self-refreshing universe + sector map
│  ├─ darwin_eval/                     # vendored Darwin DSL evaluator (option B)
│  └─ strategies/                      # OPEN (public) formulas only
├─ public/
│  ├─ data/{portfolio.json,trades.json,strategies.json,universe.json}
│  ├─ resume.pdf
│  └─ art/  audio/
├─ .github/workflows/{open-strategies-update.yml, universe-refresh.yml}
├─ docs/  plans_and_text_files/  scripts/
```

Secured formulas/weights are **not** here — they live in the private repo (§8).

---

## 10. Data contract (single source of truth: `lib/data.ts`)

`public/data/portfolio.json` (mixed open + secured):

```json
{
  "as_of": "2026-06-01",
  "base_currency": "USD",
  "strategies": [
    {
      "id": "open_momentum_v1",
      "name": "Momentum (Open)",
      "visibility": "open",
      "equity_curve": [{"d": "2026-01-02", "v": 100000.0}],
      "stats": {"cagr": 0.081, "sharpe": 0.65, "max_dd": -0.12},
      "positions": [{"ticker": "AAPL", "weight": 0.04}],
      "formula_ref": "/writing/open-momentum"
    },
    {
      "id": "balanced_king_v3",
      "name": "Balanced King",
      "visibility": "secured",
      "equity_curve": [{"d": "2026-01-02", "v": 100000.0}],
      "stats": {"cagr": 0.094, "sharpe": 0.71, "max_dd": -0.10},
      "exposure": [{"group": "Technology", "weight": 0.32},
                   {"group": "Healthcare", "weight": 0.18}]
    }
  ]
}
```

`public/data/strategies.json` (the §6.4 per-strategy metadata, published for all strategies):

```json
{
  "as_of": "2026-06-01",
  "strategies": [
    {
      "id": "balanced_king_v3",
      "name": "Balanced King",
      "visibility": "secured",
      "portfolio_size": 100000,
      "base_currency": "USD",
      "rebalance_cadence_days": 42,
      "deployed_on": "2026-05-01",
      "cost_model": {"commission_bps": 5.0, "slippage_bps": 5.0,
                     "spread_ref_price": 50.0, "volume_impact_coef": 0.5,
                     "impact_portfolio_size": 1000000, "vol_scaled_cost_enable": true,
                     "vol_cost_k": 0.75, "vol_cost_realized_window": 63,
                     "vol_cost_long_window": 252, "vol_cost_mult_max": 3.0},
      "blurb": "Balanced risk/return king from epoch 7."
    }
  ]
}
```

Rules: `visibility` gates which fields appear in `portfolio.json`. **Secured entries must never
contain `positions` or any formula.** `strategies.json` metadata is non-secret and published
for all strategies. The reader (`lib/data.ts`) and the writers (`paper_trading/` + the private
repo) change together. See `docs/concepts/data-contract.md`.

---

## 11. Optional upgrade path (only if/when needed)

| Want | Add | Cost |
|---|---|---|
| Intraday / on-demand refresh | small FastAPI service (Fly.io/Railway) | ~$5–7/mo |
| Real DB as history grows | SQLite → Postgres (Neon free) | $0+ |
| Real-money trading | broker integration, SEPARATE private box, never public | broker $$ |

Out of scope for v1. The static design covers the stated goals at ~$10/yr.

---

## 12. Step-by-step build order

1. **Buy domain** at Cloudflare; point DNS at Cloudflare.
2. **Scaffold** Next.js + Tailwind in `personal-site`; wire the dark theme + nav shell.
3. **Deploy empty site to Vercel**; confirm `https://yourdomain` resolves with TLS.
4. **Content sections first** (no moving parts): About/résumé, Writing (MDX), Studio
   (music/art), Projects. Useful immediately.
5. **Darwin section**: explainer + results, authored from real king metrics.
6. **Define the data contract** (`lib/data.ts` + hand-written sample `public/data/*.json`
   with one open + one secured entry).
7. **Build dashboard components** against the sample JSON (equity curve, stats, exposure
   donut, positions table, disclaimer). Site looks "live" before any pipeline exists.
8. **Open updater** *(done)*: `paper_trading/` engine — vendored Darwin DSL evaluator (option B),
   the Darwin-faithful cost model (`costs.py`, §6.5), the secured sanitizer (`secured.py`), and
   `open-strategies-update.yml`.
9. **Self-refreshing universe** *(done)*: `universe.py` + `update_universe.py` +
   `universe-refresh.yml` (monthly), resolved by both updaters (§7.1).
10. **Darwin deploy (Tier 3)** *(done, UI export)*: the "Deploy to site" button — `site-spec`
    endpoint + `StrategyDrawer` items — exports a king's scrubbed formula + metadata + cost model and
    stamps its cadence (§8.1). A `scripts/deploy_to_site.py` to auto-place the file is optional/later.
11. **Secured pipeline** *(in progress)*: the private repo `personal-site-trading` is scaffolded
    (`update_secured.py`, `push_to_public.py`, `daily.yml`, PAT secret); remaining: drop in a real
    secured king spec and run the daily cron end-to-end (§8).
12. **Iterate**: more strategies, drawdown chart, trade log, more writeups/art/music.

---

## 13. Security / hygiene checklist

- [ ] Website repo is **separate** from Darwin; no import path reaches `src/config/secrets.py`.
- [ ] Secret formulas and weights live **only** in the private repo; never in the public repo
      or its git history.
- [ ] Secured published JSON contains **no** `positions` and **no** formula — exposure +
      curve + stats only.
- [ ] No API keys in either repo. Keyless price sources, or a GitHub Actions **secret**.
- [ ] No trading/order/write endpoints exposed publicly. Paper sim runs in CI only.
- [ ] The private→public push copies only sanitized `public/data/*.json`.
- [ ] `.env` and credentials git-ignored; host/CI env vars used for any secrets.
- [ ] Clear "simulated paper portfolio, not investment advice" disclaimer on the live page.

---

## 14. Resolved decisions

- **Theme:** dark / technical throughout (see §5, `docs/reference/design-system.md`).
- **Nav:** grouped, Studio hub for music + art (see §4, `docs/reference/site-map.md`).
- **Secured disclosure:** aggregate sector/asset-class exposure only; never individual
  tickers (see §6). Exposure is an **approximation** — unmapped tickers bucket into "Other", and
  the live donut says so.
- **Secured auto-run:** a private GitHub repo's Actions (see §8).
- **Signal evaluation:** **option B** — Darwin's DSL evaluator vendored into
  `paper_trading/darwin_eval/` and parity-tested (see §7, §8.1). Not the lighter option A.
- **Cost model:** **Darwin-faithful** (`paper_trading/costs.py`): per-rebalance equity haircut with
  price-scaled slippage + sqrt volume impact + volatility multiplier; full params in `cost_model`
  (see §6.5, §10).
- **Sector map / grouping:** SEC-derived map imported from Darwin (`paper_trading/ticker_sectors.json`,
  ~6.2k tickers), bundled in the public engine; GICS-style sector groups, "Other" for unmapped.
- **Default `portfolio_size` / `cost_model`:** Darwin's engine defaults — `portfolio_size` $100k,
  commission/slippage `5/5` bps, `impact_portfolio_size` $1M, and the realism/vol defaults (see §6.5).
- **Rebalance cadence:** **per-strategy**, set at deploy time via `rebalance_cadence_days` in
  each strategy's metadata; a single daily workflow rebalances whichever strategies are due
  (see §8.1). No global cadence.
- **Per-strategy details:** portfolio size, base currency, cadence, cost model, blurb, deploy
  date — published in `strategies.json` (see §6.4).
- **Darwin section:** includes a Methodology subsection detailing the backtesting and cost
  models (see §6.5).
- **Tradable universe:** self-refreshing in the public repo (Nasdaq Trader listings + Darwin
  filters), rebuilt monthly, *not* snapshotted from Darwin — keeps it current and Darwin-independent
  (see §7.1, `docs/subsystems/universe.md`).
- **Darwin deploy:** a UI export button (`site-spec` endpoint + drawer items), **built** (see §8.1).

### Still open (confirm before/while building)

- Domain name + TLD.
- Which 1–2 strategies are the "open" advertisements, and which kings are secured.
- Music hosting: third-party embeds vs self-hosted audio in `public/audio/`.
