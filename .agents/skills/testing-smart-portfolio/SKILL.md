---
name: testing-smart-portfolio
description: How to run and end-to-end test the Smart Portfolio Streamlit app locally (prices, percentiles, sidebar edits, JSON persistence).
---

# Testing the Smart Portfolio Streamlit app

## Run it
```bash
cd <repo>
.venv/bin/streamlit run app.py --server.port 8501 --server.headless true > /tmp/streamlit.log 2>&1 &
```
- A `.venv` with deps is normally present; otherwise `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
- No credentials/logins are needed: data comes from public Yahoo Finance (`yfinance`) and
  `api.exchangerate-api.com`. `TWELVE_DATA_API_KEY` is an *optional* env var used only as a
  per-symbol fallback — without it that fallback branch cannot be exercised.
- Streamlit only executes `app.py` when a browser connects, so files like `stock_cache.json`
  appear only after you actually open `http://localhost:8501/` in Chrome.
- When driving Chrome via computer-use, type the full `http://localhost:8501/` URL (a bare
  `localhost:8501` in the omnibox can be mangled into an invalid `chrome://` URL).

## State files (all in repo root, all git-tracked — revert them after testing)
- `portfolio.json` — positions; must contain ONLY `symbol/shares/avg_cost/currency/fx`.
  `populate_market_data` decorates the in-memory dicts with `price/history/market_value/...`,
  so any regression in `save_portfolio` will visibly leak those keys into the file.
- `client_cash.json` — AZHU/ANIU USD+HKD balances.
- `stock_cache.json` — price+63-close history per symbol with a 1h TTL timestamp; delete it to
  force a genuine cold start, and diff its `timestamp` values to prove a refetch actually happened
  (that is the only reliable way to tell "Force Update All" from a plain rerun).
- Cleanup: `git checkout portfolio.json client_cash.json && git status --porcelain`.

## Useful adversarial checks
- Percentiles: recompute independently in the shell and compare to the on-screen numbers, e.g.
  `rank = sum(1 for p in closes[-W:] if p <= current)/W*100` with W = 5 / 21 / 63. A hardcoded or
  broken implementation will not match all three windows for several symbols.
- Adding shares to an existing symbol must blend: `(old_avg*old_sh + new_cost*new_sh)/(old_sh+new_sh)`.
  Check the number in `portfolio.json`, not just the rounded `$X.XX` in the table.
- Sidebar layout order: Edit Stock → Edit Cash → Add New Stock. The "Add New Stock" block sits
  below the fold; scroll the sidebar before clicking `Add Stock`.
- Prices may look implausible if the sandbox clock is set to a future date — that is environmental,
  not an app bug. Judge correctness by cross-checking against a fresh `yf.download` in the same env.

## Devin Secrets Needed
None. (`TWELVE_DATA_API_KEY` only if the Twelve Data fallback path must be covered.)
