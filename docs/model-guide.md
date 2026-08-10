# Model Guide

What one HarmonicCycleLab run does: load data, pick cycle lengths, fit/extrapolate the harmonic overlay, and fold SuperTrend, TD Sequential, Squeeze Momentum, and CMF into the decision note.

Code: `cycle_engine.py`. UI: `streamlit_app.py`. Period math alone: [cycle-math.md](cycle-math.md). **DFE** = Dynamic Frequency Extraction.

## Modules

| Module | Role |
|---|---|
| Cycle harmonics | Dominant residual periods → sine/cosine fit → overlay + dashed projection |
| SuperTrend | ATR band; side of market and defense level |
| TD Sequential | TD9 setup / countdown marks |
| Squeeze Momentum | Squeeze state + momentum histogram |
| CMF | Short-window money-flow confirmation |

SuperTrend for side of market, Cycle for phase, TD / Squeeze / CMF for timing and cross-checks.

## Layout

```
HarmonicCycleLab/
├── streamlit_app.py           # UI
├── cycle_engine.py            # indicators, DFE, fit, decision text
├── scripts/                   # backtests
├── archive/nya_v6_desktop.py  # legacy desktop archive
├── docs/
└── requirements.txt
```

`run_analysis()` downloads OHLCV, resolves cycle config, builds metrics, computes indicators, runs `analyze_trade_state`, then draws the Plotly figure. Change model behavior in `cycle_engine.py`.

## Pipeline

1. Date / lookback window (range, N bars, or auto scan up to `MAX_LOOKBACK_BARS`).
2. `download_ohlcv` (Yahoo).
3. `resolve_cycle_config` — optional DFE, optional lookback sweep, slice, optional second DFE.
4. `metrics_for_window` — detrend, fit, project.
5. SuperTrend / TD / Squeeze / CMF.
6. `analyze_trade_state` → decision block in the engine log (language from the UI toggle).
7. `build_plotly_chart`.

## Cycle module

Periods: manual, DFE peaks, or defaults. Fit residuals, not raw prices. Projection slope in `describe_cycle_outlook` is a **phase** read, not a calibrated odds of a price rise. Details: [cycle-math.md](cycle-math.md).

## Indicators

- **SuperTrend** — ATR band in `calculate_supertrend`.
- **TD Sequential** — setup / countdown (simplified for charting).
- **Squeeze Momentum** — Bollinger-inside-Keltner squeeze + histogram.
- **CMF** — short-window close location in the high-low range (default 10).

## Decision text

`analyze_trade_state` is rule prose synced to the panes:

- Short-window flow (CMF).
- Above SuperTrend: recent TD sell → de-risk; else combine Squeeze slope, CMF, and cycle direction.
- Below SuperTrend: TD buy may allow a small probe with an ATR stop; otherwise stay flat unless cycle is turning up as a watch.

Not a broker API.

## Related

| Doc | Content |
|---|---|
| [cycle-math.md](cycle-math.md) | Period estimation |
| [backtest-report.md](backtest-report.md) | Timing results |
| [improvement-roadmap.md](improvement-roadmap.md) | Next work |

Chinese: `*.zh.md` in this folder.
