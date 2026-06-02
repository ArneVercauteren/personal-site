# Tier 2a — building the private secured-updater repo (beginner-friendly)

> A complete, hand-held walkthrough for standing up `personal-site-trading`, the
> **private** repository that runs your secret "king" strategies and publishes only
> safe, summarized results to the public website.
>
> You do **not** need to be a Git or GitHub expert to follow this. Every concept is
> explained the first time it appears, and every step has either an exact command or
> click-by-click instructions for the GitHub website.
>
> The matching contract this repo must honour is in `docs/subsystems/secured-updater.md`.

---

## 0. The 60-second mental model (read this first)

Your project is split into **three tiers** so that secrets can never leak onto the public
internet. This guide builds **Tier 2a**, the middle-private piece.

```
TIER 3  Darwin (your PC)          → decides which strategy ("king") to publish, once.
TIER 2a personal-site-trading     → THIS GUIDE. Private. Holds the secret formula,
        (private repo)              runs the paper-trading simulation every day, and
                                    publishes only a SAFE SUMMARY to the public site.
TIER 1  personal-site             → The public website everyone can see.
        (public repo)
```

**Why a separate private repo at all?** The only truly sensitive things are (a) the
strategy's *formula* and (b) the exact *list of stocks and how much of each* it holds.
If those were on the public site, anyone could copy your strategy. So they live in a
**private** repo that nobody else can read, and that repo publishes only an *equity
curve* (a line showing the portfolio's value over time), some *headline statistics*,
and an *aggregate sector breakdown* (e.g. "32% Technology, 18% Health Care") — never the
individual stocks. That summary can't be reverse-engineered back into the formula.

**The good news:** almost all the hard logic (the simulator, the summarizer, the
safety checks) already lives in the **public** repo's `paper_trading/` folder and is
fully tested. The private repo you're about to build is *thin* — it adds only your secret
data, two short scripts, and one automated job.

---

## 1. Vocabulary you'll see in this guide

You can skim this and refer back. None of it is advanced.

| Term | Plain-English meaning |
|---|---|
| **Repository ("repo")** | A folder of files that GitHub tracks, with full history of every change. |
| **Public vs private repo** | *Public* = anyone on the internet can read it. *Private* = only you (and people you invite) can read it. We need private for the secrets. |
| **Git** | The tool that records changes to files. "Commit" = save a snapshot; "push" = upload your commits to GitHub. |
| **GitHub** | The website that stores your repos online. |
| **GitHub Actions** | GitHub's built-in robot that can run scripts for you automatically — for example, "every weekday evening, run this Python file." Free for this use. |
| **Workflow** | A `.yml` file inside `.github/workflows/` that tells GitHub Actions *what* to run and *when*. |
| **Cron** | A compact way to write a schedule, like "every weekday at 23:00". You'll see one string of numbers and stars — that's a cron schedule. |
| **CI** | "Continuous Integration" — jargon for "the automated jobs that run on GitHub." When this guide says "in CI", it means "inside a GitHub Actions run." |
| **PAT (Personal Access Token)** | A long password-like string that lets one repo's robot write to another repo. We need one so the *private* repo can publish into the *public* repo. |
| **Secret** | A value (like the PAT) you store in GitHub's settings so workflows can use it **without** ever printing it or committing it to a file. |
| **`PYTHONPATH`** | An environment variable telling Python where to find extra code. We use it to let the private repo borrow the public repo's `paper_trading/` code without copying it. |

---

## 2. What you'll have when you're done

```
personal-site-trading/        (PRIVATE — only you can see it)
├─ strategies/                # YOUR SECRETS: the king's formula + settings, one JSON per strategy
│   └─ balanced_king_v3.json
├─ weights/                   # (optional, advanced) frozen target weights — skip for v1
├─ requirements.txt           # the Python libraries the job needs
├─ update_secured.py          # script: run the simulation, then summarize it safely
├─ push_to_public.py          # script: copy the safe summary into the public website repo
└─ .github/workflows/
    └─ daily.yml              # the daily robot job that runs the two scripts above
```

The only files that contain anything sensitive are inside `strategies/` (and, if you use
it, `weights/`). Everything else is harmless.

---

## 3. Before you start — one-time setup on your computer

You need three things installed. Open **PowerShell** (Windows) and check each:

1. **Git** — run `git --version`. If you see a version number, you're set. If not,
   install from <https://git-scm.com/download/win> and accept the defaults.
2. **Python 3.12** — run `python --version`. If it's missing or older, install from
   <https://www.python.org/downloads/> (tick "Add Python to PATH" during install).
3. **A GitHub account** — if you don't have one, sign up free at <https://github.com>.

**Optional but convenient:** the GitHub CLI (`gh`), which lets you create repos from the
command line. Install from <https://cli.github.com>, then run `gh auth login` once and
follow the prompts (choose "GitHub.com" → "HTTPS" → "Login with a web browser").
If you'd rather not install it, this guide gives website-click instructions everywhere too.

> Throughout, replace `<you>` with your actual GitHub username (e.g. `arnev`).

---

## 4. Step 1 — Create the private repository

**Option A — using the website (no extra tools):**

1. Go to <https://github.com/new>.
2. **Repository name:** `personal-site-trading`.
3. **Visibility:** select **Private**. *(This is the important one — do not pick Public.)*
4. Tick **"Add a README file"** so the repo isn't empty.
5. Click **Create repository**.
6. On the new repo's page, click the green **`<> Code`** button → **HTTPS** → copy the URL.
7. In PowerShell, clone it to your computer (this downloads it so you can edit locally):
   ```powershell
   cd C:\Users\arnev\Projects
   git clone https://github.com/<you>/personal-site-trading.git
   cd personal-site-trading
   ```

**Option B — using the GitHub CLI (one command):**
```powershell
cd C:\Users\arnev\Projects
gh repo create personal-site-trading --private --clone --add-readme
cd personal-site-trading
```

You now have an empty private repo, both on GitHub and as a folder on your PC. From here,
you'll create the files in step 5–11, then `git add` / `git commit` / `git push` them up.

> **How to save your work to GitHub at any point** (you'll repeat this whenever you change files):
> ```powershell
> git add .
> git commit -m "describe what you changed"
> git push
> ```

---

## 5. Step 2 — Tell the private repo which Python libraries it needs

Create a file named `requirements.txt` with this content:

```
pandas
numpy
yfinance
```

These are the same libraries the public engine uses. `yfinance` downloads daily stock
prices for free with no API key — that's why this whole system costs nothing to run.

---

## 6. Step 3 — The sector lookup (already done for you)

The summarizer needs a table mapping each stock symbol to a sector name, so it can turn
"we hold 6% AAPL, 5.5% MSFT…" into "Information Technology 32%". **You don't have to create
this** — a ready-made map of ~6,200 US tickers (imported from Darwin's SEC-derived
classification) ships inside the public engine at `paper_trading/ticker_sectors.json`, and the
summarizer loads it automatically. There's nothing to do in this step unless you want to
override it.

A few things to know:

- It's **not secret** (sector classifications are public), which is why it lives in the public
  engine rather than here — both the open and secured updaters share the one file.
- Any stock that isn't in the map (or has no known sector) is counted under an **"Other"**
  slice rather than causing an error. The published breakdown is therefore an **approximation**
  — so the website's live dashboard carries a short "sector breakdown is approximate" note next
  to the donut.
- If you ever want to force a specific stock into a specific sector, you can pass your own map,
  but for v1 you don't need to.

---

## 7. Step 4 — Create the secret strategy file `strategies/balanced_king_v3.json`

This is the **one genuinely secret file**. It describes the strategy: its formula and the
settings the simulation runs under. Create a folder `strategies/` and inside it a file
named after your strategy's id (here `balanced_king_v3.json`):

```json
{
  "id": "balanced_king_v3",
  "name": "Balanced King",
  "visibility": "secured",
  "blurb": "Balanced risk/return king from epoch 7.",
  "deployed_on": "2026-05-01",
  "next_rebalance_date": "2026-06-12",
  "portfolio_size": 100000,
  "base_currency": "USD",
  "rebalance_cadence_days": 42,
  "cost_model": {
    "commission_bps": 1.0,
    "slippage_bps": 5.0,
    "spread_ref_price": 50.0,
    "volume_impact_coef": 0.5,
    "vol_scaled_cost_enable": true,
    "vol_cost_k": 0.75,
    "vol_cost_realized_window": 63,
    "vol_cost_long_window": 252,
    "vol_cost_mult_max": 3.0
  },
  "universe": ["AAPL", "MSFT", "NVDA", "JPM", "XOM", "UNH", "JNJ", "PG"],
  "formula": { "...": "the scrubbed DSL tree — see the note below" }
}
```

What each field means:

| Field | Meaning |
|---|---|
| `id` | A unique short name; also the filename. The public site uses this to know which entry to update. |
| `name` | The human-readable name shown on the site. |
| `visibility` | Must be `"secured"`. This is what tells every safety check "never reveal the holdings." |
| `blurb` | One-line description shown on the site. |
| `deployed_on` | The date the strategy "went live" — the simulation starts here. |
| `next_rebalance_date` | The next date the strategy is due to reconsider its holdings. |
| `portfolio_size` | The pretend starting capital (e.g. $100,000). It's simulated — no real money. |
| `base_currency` | The currency, e.g. `USD`. |
| `rebalance_cadence_days` | How often it rebalances, in days (42 ≈ every 6 weeks). |
| `cost_model` | The Darwin cost model: commission + slippage in basis points (1 bp = 0.01%), plus price-scaled slippage, volume-impact, and volatility-scaling parameters. These match the costs the strategy was backtested under in Darwin. Only `commission_bps`/`slippage_bps` are required; the rest default to Darwin's engine values. |
| `universe` | The list of stocks the strategy is allowed to choose from. |
| `formula` | The actual strategy logic, as a structured "tree." **This is the secret.** |

> **Where does `formula` come from?** It's generated by a script called `deploy_to_site.py`
> in your Darwin project (that's Tier 3, a separate future step). Until that script exists,
> you can hand-paste a formula tree here just to test that the pipeline runs end to end. The
> rest of this guide works the same either way.

---

## 8. Step 5 — Create `update_secured.py` (run the simulation, then summarize it)

This script is the heart of Tier 2a. For each strategy file it:
1. downloads the needed price history,
2. runs the **same simulator** the public site already uses,
3. **summarizes** the result into the safe form (curve + stats + sector breakdown),
4. saves that summary to a temporary file called `_snapshot.json`.

Crucially, the summarizing function (`build_secured_entry`) automatically runs a **leak
check**: if anything tried to include the individual holdings or the formula, the script
**crashes here** — before anything is ever published. That's your safety net.

```python
import json
from pathlib import Path
import pandas as pd
from paper_trading import portfolio, prices                  # borrowed from the public repo
from paper_trading.secured import build_secured_entry
from paper_trading.darwin_eval.select_on_date import (
    collect_all_needed_features, required_history_days,
)

ROOT = Path(__file__).resolve().parent
WARMUP_DAYS = 400   # extra history so the first signal has enough lookback

def run():
    portfolio_entries, meta_entries = [], []
    latest = ""
    for path in sorted((ROOT / "strategies").glob("*.json")):
        spec = json.loads(path.read_text())
        assert spec["visibility"] == "secured", path
        end = pd.Timestamp.today().strftime("%Y-%m-%d")
        needed = collect_all_needed_features(spec["formula"], include_exit_root=True)
        warmup = max(WARMUP_DAYS, int(required_history_days(needed) * 1.6) + 30)
        start = (pd.Timestamp(spec["deployed_on"]) - pd.Timedelta(days=warmup)).strftime("%Y-%m-%d")
        long = prices.get_ohlcv(spec["universe"], start, end)
        opens, closes = prices.long_to_wide(long)
        sim = portfolio.simulate(spec, opens, closes, prices_long=long)
        latest = max(latest, sim.as_of)

        # Drops the individual stocks, buckets unknowns into "Other", and refuses
        # to leak the formula. Uses the engine's bundled sector map by default.
        portfolio_entries.append(build_secured_entry(sim, spec))
        meta_entries.append({
            "id": spec["id"], "name": spec["name"], "visibility": "secured",
            "portfolio_size": spec["portfolio_size"], "base_currency": spec["base_currency"],
            "rebalance_cadence_days": spec["rebalance_cadence_days"],
            "deployed_on": spec["deployed_on"], "cost_model": spec["cost_model"],
            "blurb": spec["blurb"],
        })

    snapshot = {"as_of": latest, "portfolio": portfolio_entries, "strategies": meta_entries}
    (ROOT / "_snapshot.json").write_text(json.dumps(snapshot, indent=2))
    print(f"sanitized {len(portfolio_entries)} secured strategies; as_of={latest}")

if __name__ == "__main__":
    run()
```

`_snapshot.json` contains **only** safe summary data, so it's harmless — but it's just a
temporary build artifact, so tell Git to ignore it. Create a file named `.gitignore` with:

```
_snapshot.json
__pycache__/
```

---

## 9. Step 6 — Create `push_to_public.py` (copy the summary into the public site)

This script takes the safe `_snapshot.json` and writes it into the **public** repo's data
files. It "merges by id," meaning it updates only *your* secured strategies and leaves the
public site's *open* strategies untouched — so the two halves never overwrite each other.

```python
import json, sys
from pathlib import Path
from paper_trading.update import merge_by_id   # borrowed helper from the public repo

PUBLIC = Path(sys.argv[1])                      # path to the checked-out public repo
snap = json.loads((Path(__file__).parent / "_snapshot.json").read_text())
ids = {e["id"] for e in snap["portfolio"]}
data = PUBLIC / "public" / "data"

pf = json.loads((data / "portfolio.json").read_text())
pf["as_of"] = max(snap["as_of"], pf.get("as_of", ""))
pf["strategies"] = merge_by_id(pf["strategies"], snap["portfolio"], ids)
(data / "portfolio.json").write_text(json.dumps(pf, indent=2) + "\n")

meta = json.loads((data / "strategies.json").read_text())
meta["as_of"] = max(snap["as_of"], meta.get("as_of", ""))
meta["strategies"] = merge_by_id(meta["strategies"], snap["strategies"], ids)
(data / "strategies.json").write_text(json.dumps(meta, indent=2) + "\n")
print(f"merged {len(ids)} secured entries into public/data")
```

(Secured strategies deliberately do **not** write a public trade log, so this script never
touches `trades.json`.)

---

## 10. Step 7 — Test everything on your own computer first

Before involving any automation, prove the two scripts work locally. This avoids debugging
inside GitHub Actions, which is slower.

1. Make sure the public repo is also cloned next to this one (you already have it at
   `C:\Users\arnev\Projects\Personal_Site`).
2. In PowerShell, from the private repo folder, install the libraries and point Python at
   the public engine, then run the scripts:
   ```powershell
   cd C:\Users\arnev\Projects\personal-site-trading
   pip install -r requirements.txt
   $env:PYTHONPATH = "C:\Users\arnev\Projects\Personal_Site"   # lets Python find paper_trading/
   python update_secured.py                                    # creates _snapshot.json
   python push_to_public.py "C:\Users\arnev\Projects\Personal_Site"
   ```
3. Open `C:\Users\arnev\Projects\Personal_Site\public\data\portfolio.json` and confirm your
   secured strategy now appears with an `exposure` list — and **no** `positions` and **no**
   `formula`. If the script crashed with a leak error, that's the safety net doing its job;
   read the message, fix the cause, and re-run.

> Any stock not in the bundled sector map shows up under an **"Other"** slice — that's expected
> and harmless (the breakdown is an approximation). Nothing to fix.

Once this works locally, you're ready to automate it. (Don't commit the public repo's changed
JSON by hand — the automation will do that. You can discard your local test edit with
`git checkout public/data` inside the public repo.)

---

## 11. Step 8 — Create the access token (so the robot can publish)

The daily robot lives in the **private** repo but must *write into the public repo*. GitHub
won't allow that without permission, so you create a **fine-grained Personal Access Token**
scoped to only the public repo.

Click-by-click:

1. Go to <https://github.com/settings/personal-access-tokens/new> (Settings → Developer
   settings → Personal access tokens → **Fine-grained tokens** → **Generate new token**).
2. **Token name:** `secured-updater-push`.
3. **Expiration:** pick something like 90 days or 1 year (you'll regenerate it when it expires).
4. **Resource owner:** your own account.
5. **Repository access:** choose **Only select repositories**, then pick **`personal-site`**
   (the public one) — *not* the private one.
6. **Permissions:** expand **Repository permissions**, find **Contents**, and set it to
   **Read and write**. Leave everything else as "No access."
7. Click **Generate token**, then **copy the token string now** — GitHub shows it only once.

Keep it on your clipboard for the next step. (If you lose it, just generate a new one.)

---

## 12. Step 9 — Store the token as a secret in the private repo

This lets the workflow use the token **without ever writing it into a file**.

1. Go to your **private** repo on GitHub: `https://github.com/<you>/personal-site-trading`.
2. **Settings** (top tab) → in the left sidebar, **Secrets and variables** → **Actions**.
3. Click **New repository secret**.
4. **Name:** `PUBLIC_REPO_PAT` (exactly — the workflow refers to this name).
5. **Secret:** paste the token you copied.
6. Click **Add secret**.

That's the only secret you need. Price data is keyless, so there's nothing else to configure.

---

## 13. Step 10 — Create the daily robot job `.github/workflows/daily.yml`

Create the folders `.github/workflows/` and inside them a file `daily.yml`. This tells
GitHub Actions: every weekday evening, check out both repos, run the two scripts, and push
the result to the public site.

```yaml
name: Secured — daily mark & push
on:
  schedule:
    - cron: "0 23 * * 1-5"     # 23:00 UTC, Monday–Friday (after the US market closes)
  workflow_dispatch: {}         # also lets you run it manually with a button
concurrency: { group: secured-daily, cancel-in-progress: false }
jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4                 # download THIS private repo

      - uses: actions/checkout@v4                 # also download the PUBLIC repo (the engine + site)
        with:
          repository: <you>/personal-site
          path: public-site                       # put it in a subfolder called public-site
          token: ${{ secrets.PUBLIC_REPO_PAT }}   # the token from step 9, used to push later

      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }

      - run: pip install -r requirements.txt
      - run: echo "PYTHONPATH=${{ github.workspace }}/public-site" >> $GITHUB_ENV  # find paper_trading/

      - name: Simulate + summarize
        run: python update_secured.py

      - name: Merge into public data
        run: python push_to_public.py public-site

      - name: Commit & push to the public repo
        working-directory: public-site
        run: |
          git config user.name "secured-trading-bot"
          git config user.email "actions@users.noreply.github.com"
          git add public/data/portfolio.json public/data/strategies.json
          if git diff --staged --quiet; then
            echo "no secured changes today"
          else
            git commit -m "data: refresh secured paper portfolio [skip ci]"
            git push
          fi
```

Remember to replace `<you>` with your GitHub username in the `repository:` line.

**Reading the cron line:** `"0 23 * * 1-5"` is five fields: minute (0), hour (23), day-of-month
(any), month (any), day-of-week (1-5 = Mon–Fri). So: "at 23:00 UTC on weekdays." You can paste
a cron string into <https://crontab.guru> to see it in plain English.

---

## 14. Step 11 — Push everything and run it once by hand

1. Save all your work to GitHub:
   ```powershell
   cd C:\Users\arnev\Projects\personal-site-trading
   git add .
   git commit -m "Tier 2a: secured updater scripts + daily workflow"
   git push
   ```
2. On GitHub, open the private repo → **Actions** tab. You'll see the workflow
   "Secured — daily mark & push" listed.
3. Click it, then click **Run workflow** (the manual-trigger button, available because of the
   `workflow_dispatch:` line). This runs it immediately instead of waiting for the schedule.
4. Watch the run. Green check = success. If a step is red, click it to read the error log.
5. On success, open the **public** repo and confirm `public/data/portfolio.json` shows your
   secured strategy's updated `exposure`. Vercel will redeploy the site automatically.

From now on it runs itself every weekday evening. You only come back here to deploy a new
strategy or rotate the token when it expires.

---

## 15. (Optional, advanced) The separate "rebalance" job

The original plan mentioned a second workflow (`rebalance.yml`) and a `weights/` folder. **You
can safely skip this for v1.** Here's why: the simulator re-computes the *entire* history from
scratch on every run, so it's already correct each day without remembering anything between
runs.

The separate rebalance job only matters if you later want to *freeze* the exact target weights
on each rebalance date (so the daily mark uses the actually-held weights rather than
re-deriving them). If you go there, the public engine already ships the two helper functions
you'd need:

```python
from paper_trading.secured import is_rebalance_due, advance_next_rebalance
# inside a rebalance script, for each strategy:
if is_rebalance_due(spec["next_rebalance_date"], today):
    # ... evaluate the formula → write weights/<id>.json ...
    spec["next_rebalance_date"] = advance_next_rebalance(
        spec["next_rebalance_date"], spec["rebalance_cadence_days"], today)
    # ... save the updated spec ...
```

---

## 16. Safety checklist — confirm before trusting the first public push

- [ ] The repo is **Private** (check the badge next to its name on GitHub).
- [ ] `strategies/` and `weights/` exist **only** in this private repo — never copied into `personal-site`.
- [ ] The workflow's commit step adds **only** `public/data/portfolio.json` and `strategies.json`.
- [ ] In the published `portfolio.json`, your secured entry has an `exposure` list and **no** `positions`, **no** `formula`, **no** `formula_ref`. (The script enforces this, but eyeball it once.)
- [ ] `PUBLIC_REPO_PAT` is a **fine-grained** token, scoped to **only** `personal-site`, with **Contents: read & write** and nothing else.

---

## 17. Common problems and fixes

| Symptom | Likely cause / fix |
|---|---|
| `ModuleNotFoundError: No module named 'paper_trading'` | `PYTHONPATH` isn't pointing at the public repo. Locally: re-run the `$env:PYTHONPATH = ...` line. In CI: check the `echo "PYTHONPATH=..."` step and the `path: public-site` checkout. |
| A held stock shows under "Other" | Expected — it isn't in the bundled sector map. The breakdown is an approximation. Override the map only if you care about that one stock's classification. |
| `SecuredLeakError: ... would leak ['positions']` | The safety net fired — good. It means something tried to publish holdings. Don't bypass it; find what added the field. |
| Workflow step "Commit & push" fails with a permissions/403 error | The token is wrong or under-scoped. Re-check step 8 (Contents: read & write, correct repo) and that the secret name is exactly `PUBLIC_REPO_PAT`. |
| `git push` rejected ("non-fast-forward") | The public repo changed since checkout (e.g. the open updater pushed). Just re-run the workflow; the next run checks out the latest. |
| The site doesn't update after a successful push | Give Vercel a minute to redeploy, then hard-refresh. Confirm the JSON actually changed in the public repo. |

---

## 18. How this maps to the public engine you already have

The private repo is thin because all the real logic is the public, tested engine:

| Private repo needs | Provided by (public repo, already built) |
|---|---|
| Simulate a strategy | `paper_trading.portfolio.simulate(..., prices_long=...)` |
| Download price history | `paper_trading.prices.get_ohlcv` / `long_to_wide` |
| Work out how much history to fetch | `paper_trading.darwin_eval.select_on_date.{collect_all_needed_features, required_history_days}` |
| Turn holdings into a sector breakdown | `paper_trading.secured.aggregate_exposure` |
| Build the safe summary + run the leak check | `paper_trading.secured.build_secured_entry` / `assert_sanitized` |
| Decide which strategies are due to rebalance (optional) | `paper_trading.secured.is_rebalance_due` / `advance_next_rebalance` |
| Update public data without clobbering open strategies | `paper_trading.update.merge_by_id` |

So your job in the private repo is just: provide the secret data, wire two short scripts, add
one workflow, and store one token. Everything that touches money-logic or the safety boundary
is the code that's already shipped and tested in `personal-site`.
