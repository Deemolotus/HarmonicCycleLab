# Improvement Roadmap

Until there is real out-of-sample evidence, treat HarmonicCycleLab as a charting / research app, not a proven trading system. The long Chinese checklist with checkboxes is in [improvement-roadmap.zh.md](improvement-roadmap.zh.md).

## Aims

1. Labels match the math (phase overlay ≠ price target).
2. Published forecasts are walk-forward reproducible.
3. High / medium / low confidence comes from held-out hit rates, not hand-picked R² cuts.
4. Any buy/sell wording assumes next-bar fills, costs, and risk.

## Baseline (old direction checks)

On Yahoo daily bars (notes through mid-2026), raw cycle *direction* hit rates for VOO/QQQ at 5/20/65-day horizons sat near chance and lagged an always-long baseline on those ETFs. In-sample R² did not lift forward hit rates. Use balanced accuracy and serious baselines before claiming skill.

Separate **timing** backtests (multi-factor grid vs buy-and-hold) are in [backtest-report.md](backtest-report.md). Those score a long/cash rule, not the phase-direction table above.

## Workstreams

### P0 — Fix meaning first

- Chart/copy: phase projection vs price forecast.
- Per-period source tags (`dfe` / `fallback` / `manual`), not one global tag.
- Don’t pad to three periods and call it a successful DFE.
- Causal evaluation only (no peeking; next-bar economics).

### P1 — Evaluation

- Walk-forward / purged splits.
- Balanced accuracy, profit factor, drawdown, exposure — not accuracy alone.
- Calibrate confidence on held-out eras.

### P2 — Model changes (after P0/P1)

- Optional full log-price model: trend + cycle (+ residual).
- Richer flow / risk overlays.
- Sector-aware defaults where timing historically helped.

### P3 — Product

- Keep Streamlit copy, titles, downloads, and logs aligned.
- Regression tests for causality and labeling.

Finish P0 before retuning weights on in-sample Sharpe. After engine changes, re-run `scripts/run_backtest_ablation.py` and refresh `docs/data/backtest_master.json`.
