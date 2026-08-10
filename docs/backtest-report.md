# Backtest Report

Walk-forward timing results for HarmonicCycleLab. Numbers live in `docs/data/backtest_master.json`; regenerate with `scripts/run_backtest_ablation.py`.

## Method

At each daily close the engine builds four component scores on approximately \([-1, 1]\):

- **TD** — recent TD9 buy/sell events with exponential decay
- **Cycle** — harmonic fit on a detrended historical window; direction from the projection slope, with a soft penalty near projected peaks
- **CMF** — short-window money flow (CMF), tanh-scaled
- **SuperTrend** — +1 above the band, −1 below

The combined score is

```text
score = w_td·TD + w_cycle·Cycle + w_cmf·CMF + w_st·SuperTrend
```

When `score ≥ threshold`, the strategy goes long on the next close; otherwise it holds cash (long-only). Turnover is charged at 5 bps per side.

Cycle lengths come from either:

| Setting | Definition |
|---|---|
| Fixed periods | Always `[127, 227, 78]` trading days |
| DFE | Re-estimate three dominant periods from the residual periodogram at each refresh |

**Grid-best** searches weights on the simplex (with local refinement) and keeps the in-sample Sharpe maximum.  
**Cycle-only** fixes Cycle weight at 100% and sweeps thresholds only.

Shared settings: Yahoo Finance daily bars; history from about 2014 (later for XLC/XLRE); 400-bar warmup; 505-bar lookback; cycle score refreshed every 5 bars. Buy-and-hold and the strategy share the same evaluation window after warmup.

## Caveat

Grid-best weights were picked on the same sample that is scored, so those rows are optimistically biased. Compare rank order across tickers/settings; don’t treat one cell’s total return as a live edge.

## Table A — Grid-best: fixed periods vs DFE

| Ticker | Name | BH total | BH Sharpe | BH max DD | Fixed total | Fixed Sharpe | Fixed DD | Fixed weights TD/Cy/CMF/ST@thr | DFE total | DFE Sharpe | DFE DD | DFE weights | Sharpe Δ (DFE−fixed) | Fixed beats BH total | DFE beats BH total |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---:|:---:|:---:|
| QQQ | Nasdaq-100 ETF | 543% | 0.87 | -36% | 345% | 1.15 | -13% | `0.80/0.00/0.00/0.20@0.05` | 298% | 1.23 | -11% | `0.70/0.10/0.10/0.10@0.1` | +0.08 | N | N |
| VOO | S&P 500 ETF | 269% | 0.75 | -34% | 110% | 0.89 | -11% | `0.40/0.00/0.20/0.40@0.25` | 110% | 0.89 | -11% | `0.40/0.00/0.20/0.40@0.25` | -0.00 | N | N |
| GLD | Gold | 284% | 0.83 | -26% | 144% | 1.00 | -10% | `0.30/0.30/0.40/0.00@0.1` | 73% | 0.90 | -8% | `0.40/0.40/0.20/0.00@0.3` | -0.10 | N | N |
| IWM | Russell 2000 | 145% | 0.47 | -42% | 174% | 0.84 | -17% | `0.80/0.10/0.00/0.10@0.1` | 192% | 0.79 | -16% | `0.40/0.20/0.20/0.20@0.1` | -0.05 | Y | Y |
| XLC | Communication Services | 97% | 0.57 | -47% | 74% | 0.82 | -15% | `0.10/0.30/0.10/0.50@0.25` | 125% | 0.77 | -35% | `1.00/0.00/0.00/0.00@0.0` | -0.05 | N | Y |
| XLK | Technology | 781% | 0.94 | -34% | 421% | 1.08 | -24% | `0.40/0.20/0.00/0.40@0.0` | 237% | 1.17 | -13% | `0.40/0.20/0.10/0.30@0.3` | +0.09 | N | N |
| XLF | Financials | 182% | 0.54 | -43% | 94% | 0.58 | -24% | `0.00/0.00/0.50/0.50@0.05` | 188% | 0.65 | -28% | `0.20/0.40/0.00/0.40@0.0` | +0.07 | N | Y |
| XLE | Energy | 77% | 0.32 | -70% | 317% | 0.82 | -23% | `0.00/0.50/0.20/0.30@0.05` | 206% | 0.70 | -24% | `0.00/0.50/0.50/0.00@0.15` | -0.12 | Y | Y |
| XLV | Health Care | 117% | 0.51 | -29% | 54% | 0.61 | -17% | `1.00/0.00/0.00/0.00@0.35` | 107% | 0.62 | -18% | `0.70/0.10/0.00/0.20@0.05` | +0.01 | N | N |
| XLI | Industrials | 241% | 0.66 | -43% | 105% | 0.67 | -13% | `0.00/0.00/0.50/0.50@0.1` | 107% | 0.67 | -16% | `0.00/0.10/0.40/0.50@0.15` | +0.00 | N | N |
| XLY | Consumer Discretionary | 201% | 0.56 | -40% | 143% | 0.53 | -39% | `1.00/0.00/0.00/0.00@0.0` | 69% | 0.57 | -20% | `0.40/0.40/0.00/0.20@0.25` | +0.04 | N | N |
| XLP | Consumer Staples | 67% | 0.39 | -25% | 70% | 0.44 | -23% | `1.00/0.00/0.00/0.00@0.0` | 66% | 0.62 | -17% | `0.60/0.40/0.00/0.00@0.35` | +0.19 | Y | N |
| XLU | Utilities | 98% | 0.42 | -37% | 97% | 0.45 | -36% | `1.00/0.00/0.00/0.00@0.0` | 247% | 1.06 | -18% | `0.50/0.50/0.00/0.00@0.2` | +0.60 | N | Y |
| XLB | Materials | 130% | 0.47 | -40% | 121% | 0.51 | -36% | `0.00/1.00/0.00/0.00@0.0` | 49% | 0.39 | -16% | `1.00/0.00/0.00/0.00@0.05` | -0.12 | N | N |
| XLRE | Real Estate | 41% | 0.28 | -39% | 57% | 0.37 | -33% | `1.00/0.00/0.00/0.00@0.0` | 57% | 0.37 | -33% | `1.00/0.00/0.00/0.00@0.0` | -0.00 | Y | Y |

Using a ±0.01 tolerance, DFE Sharpe is higher for 6/15 names, lower for 5/15, and similar for 4/15. Total-return wins vs buy-and-hold: fixed 4/15, DFE 6/15. Sharpe wins vs buy-and-hold: fixed 14/15, DFE 14/15.

DFE helps most clearly on Utilities (XLU), Communication Services (XLC), and Financials (XLF). On Gold (GLD), Materials (XLB), and Energy (XLE), fixed default periods are often competitive or better.

## Table B — Cycle-only: fixed vs DFE

| Ticker | BH Sharpe | Fixed cyc total | Fixed cyc Sharpe | Fixed DD | DFE cyc total | DFE cyc Sharpe | DFE DD | Sharpe Δ | Fixed beats BH | DFE beats BH |
|---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|:---:|
| QQQ | 0.87 | 160% | 0.57 | -44% | 311% | 0.97 | -17% | +0.40 | N | N |
| VOO | 0.75 | 113% | 0.52 | -29% | 101% | 0.63 | -15% | +0.11 | N | N |
| GLD | 0.83 | 90% | 0.64 | -15% | 102% | 0.86 | -13% | +0.22 | N | N |
| IWM | 0.47 | 83% | 0.41 | -28% | 145% | 0.58 | -26% | +0.17 | N | N |
| XLC | 0.57 | 66% | 0.51 | -39% | -3% | 0.06 | -43% | -0.44 | N | N |
| XLK | 0.94 | 323% | 0.76 | -36% | 484% | 0.98 | -24% | +0.22 | N | N |
| XLF | 0.54 | 54% | 0.30 | -47% | 64% | 0.35 | -29% | +0.05 | N | N |
| XLE | 0.32 | 57% | 0.30 | -61% | 50% | 0.29 | -38% | -0.01 | N | N |
| XLV | 0.51 | 26% | 0.23 | -31% | 63% | 0.42 | -25% | +0.19 | N | N |
| XLI | 0.66 | 93% | 0.45 | -37% | 69% | 0.44 | -33% | -0.00 | N | N |
| XLY | 0.56 | 103% | 0.43 | -42% | 74% | 0.43 | -29% | -0.01 | N | N |
| XLP | 0.39 | 33% | 0.27 | -25% | 59% | 0.49 | -20% | +0.22 | N | N |
| XLU | 0.42 | 56% | 0.34 | -35% | 222% | 0.99 | -16% | +0.65 | N | Y |
| XLB | 0.47 | 121% | 0.51 | -36% | -12% | -0.02 | -37% | -0.53 | N | N |
| XLRE | 0.28 | 38% | 0.29 | -36% | 0% | 0.07 | -34% | -0.21 | N | N |

Cycle-only configs usually underperform the multi-factor grid on Sharpe and draw larger drawdowns. DFE can improve cycle-only results for some names (e.g. XLU), but cycle projection alone is a weak trading rule in this setup.

## Table C — Best Sharpe across the four settings

| Ticker | Buy & hold | Fixed+grid | DFE+grid | Fixed+cycle | DFE+cycle | Winner |
|---|---:|---:|---:|---:|---:|---|
| QQQ | 0.87 | 1.15 | 1.23 | 0.57 | 0.97 | DFE+grid |
| VOO | 0.75 | 0.89 | 0.89 | 0.52 | 0.63 | Fixed+grid |
| GLD | 0.83 | 1.00 | 0.90 | 0.64 | 0.86 | Fixed+grid |
| IWM | 0.47 | 0.84 | 0.79 | 0.41 | 0.58 | Fixed+grid |
| XLC | 0.57 | 0.82 | 0.77 | 0.51 | 0.06 | Fixed+grid |
| XLK | 0.94 | 1.08 | 1.17 | 0.76 | 0.98 | DFE+grid |
| XLF | 0.54 | 0.58 | 0.65 | 0.30 | 0.35 | DFE+grid |
| XLE | 0.32 | 0.82 | 0.70 | 0.30 | 0.29 | Fixed+grid |
| XLV | 0.51 | 0.61 | 0.62 | 0.23 | 0.42 | DFE+grid |
| XLI | 0.66 | 0.67 | 0.67 | 0.45 | 0.44 | DFE+grid |
| XLY | 0.56 | 0.53 | 0.57 | 0.43 | 0.43 | DFE+grid |
| XLP | 0.39 | 0.44 | 0.62 | 0.27 | 0.49 | DFE+grid |
| XLU | 0.42 | 0.45 | 1.06 | 0.34 | 0.99 | DFE+grid |
| XLB | 0.47 | 0.51 | 0.39 | 0.51 | -0.02 | Fixed+grid |
| XLRE | 0.28 | 0.37 | 0.37 | 0.29 | 0.07 | Fixed+grid |

Winner counts: DFE+grid 8; Fixed+grid 7. Neither cycle-only setting wins any ticker.

## Discussion

1. The multi-factor grid dominates cycle-only; harmonics are better as a phase overlay than as the sole position switch.
2. DFE helps on some sectors but is not a universal upgrade—keep fixed defaults as a baseline.
3. On strong secular bull ETFs (QQQ, VOO, XLK), staying in cash forfeits a large share of absolute return even when Sharpe improves.
4. Energy, small-caps, and some rate-sensitive sectors more often allow timing to beat buy-and-hold on total return, consistent with weaker drift and deeper drawdowns.

Rolling OOS and cost sensitivity are still open — see `docs/improvement-roadmap.md`.

## Reproduction

```bash
python scripts/run_backtest_ablation.py
python scripts/run_strategy_backtest.py --symbol XLE --use-dfe
python scripts/run_strategy_backtest.py --symbol XLE --cycle-only
```
