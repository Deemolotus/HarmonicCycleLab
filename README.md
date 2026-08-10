# HarmonicCycleLab

[中文说明](README_zh.md)

Streamlit app that plots harmonic cycle overlays together with SuperTrend, TD Sequential, Squeeze Momentum, and a short-window money-flow pane. Yahoo Finance supplies OHLCV; `cycle_engine.py` fits cycles (fixed periods or DFE), projects them, and writes a short decision note to the engine log.

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Open http://localhost:8501, pick a symbol, hit Run. First auto-lookback pass can take half a minute to a minute and a half.

## Layout

```text
HarmonicCycleLab/
├── streamlit_app.py              # UI
├── cycle_engine.py               # indicators, DFE, fit, decision text
├── scripts/
│   ├── run_strategy_backtest.py
│   └── run_backtest_ablation.py
├── docs/
│   ├── model-guide.md
│   ├── cycle-math.md
│   ├── backtest-report.md
│   └── improvement-roadmap.md
└── requirements.txt
```

Manual periods or DFE; SuperTrend on the main pane; TD markers; Squeeze + CMF panes; language switch (EN / 中文) for UI and decision text.

## Timing backtest (sketch)

Daily long/cash rule. Four scores roughly in \([-1,1]\) (TD, Cycle, CMF, SuperTrend), long the next close when their weighted sum clears a threshold. Periods fixed at `[127, 227, 78]` or refreshed by DFE. Grid search picks in-sample Sharpe-max weights; a cycle-only run puts all weight on Cycle. 5 bps per side. Shared window after a 400-bar warmup. Numbers: [docs/backtest-report.md](docs/backtest-report.md).

## Sample results

In-sample grid-best Sharpe (same sample that chose the weights — not OOS):

| Ticker | Setting | BH Sharpe | Strategy Sharpe | Strategy total | BH total |
|---|---|---:|---:|---:|---:|
| XLE | Fixed + grid | 0.32 | 0.82 | +317% | +77% |
| XLU | DFE + grid | 0.42 | 1.06 | +247% | +98% |
| QQQ | DFE + grid | 0.87 | 1.23 | +298% | +543% |
| IWM | Fixed + grid | 0.47 | 0.84 | +174% | +145% |
| XLK | DFE + grid | 0.94 | 1.17 | +237% | +781% |

## Docs

- [model-guide.md](docs/model-guide.md) — pipeline
- [cycle-math.md](docs/cycle-math.md) — period estimation
- [backtest-report.md](docs/backtest-report.md) — tables
- [improvement-roadmap.md](docs/improvement-roadmap.md) — next work

Chinese: `*.zh.md` next to each file.

## References

Achelis, S. B. (2001). *Technical analysis from A to Z* (2nd ed.). McGraw-Hill. (ISBN 978-0-07-136348-8) 

Carter, J. F. (2005). *Mastering the trade: Proven techniques for profiting from intraday and swing trading setups*. McGraw-Hill. (ISBN 978-0-07-145958-7)

DeMark, T. R. (1994). *The new science of technical analysis*. John Wiley & Sons. (ISBN 978-0-471-03548-0) 

Hurst, J. M. (1970). *The profit magic of stock transaction timing*. Prentice-Hall. (ISBN 978-0-13-095075-8) 

Seban, O. (2009). *Tout le monde mérite d'être riche* (2nd ed.). Maxima. (ISBN 978-2-84001-618-2) 

Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power spectra: A method based on time averaging over short, modified periodograms. *IEEE Transactions on Audio and Electroacoustics, 15*(2), 70–73. https://doi.org/10.1109/TAU.1967.1161901

Wilder, J. W., Jr. (1978). *New concepts in technical trading systems*. Trend Research. (ISBN 978-0-89459-027-6) 

Not investment advice. Backtests skip live frictions and can overfit.

## License

MIT — see [LICENSE](LICENSE).
