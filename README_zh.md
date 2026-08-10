# HarmonicCycleLab

[English](README.md)

Streamlit 图表工具：谐波周期叠加，外加 SuperTrend、TD Sequential、Squeeze Momentum 和短窗资金流副图。数据来自 Yahoo Finance；核心在 `cycle_engine.py`（固定周期或 DFE 拟合、投影，并在引擎日志里写一段决策说明）。

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

打开 http://localhost:8501，选标的点运行。第一次自动 lookback 大概要半分钟到一分半。

## 目录

```text
HarmonicCycleLab/
├── streamlit_app.py              # 界面
├── cycle_engine.py               # 指标、DFE、拟合、决策
├── scripts/
│   ├── run_strategy_backtest.py
│   └── run_backtest_ablation.py
├── docs/
│   ├── model-guide.zh.md
│   ├── cycle-math.zh.md
│   ├── backtest-report.zh.md
│   └── improvement-roadmap.zh.md
└── requirements.txt
```

支持手动周期或 DFE、主图 SuperTrend、TD 标记、Squeeze / CMF 副图；侧边栏可切 EN / 中文（界面和决策文案一起切）。

## 择时回测（摘要）

日线只做多/持现金。收盘后算四个约 \([-1,1]\) 的分量（TD、Cycle、CMF、SuperTrend），加权和过阈值则下一根收盘做多。周期用固定 `[127, 227, 78]` 或每次 DFE。网格按样本内夏普选权重；仅周期对照把 Cycle 设为 100%。单边 5bps。warmup 400 根后与买入持有同一评估窗。详表见 [docs/backtest-report.zh.md](docs/backtest-report.zh.md)。

## 部分结果

样本内网格最优夏普（权重与评分同一样本，非样本外）：

| 标的 | 设定 | BH 夏普 | 策略夏普 | 策略总收益 | BH 总收益 |
|---|---|---:|---:|---:|---:|
| XLE | 固定 + 网格 | 0.32 | 0.82 | +317% | +77% |
| XLU | DFE + 网格 | 0.42 | 1.06 | +247% | +98% |
| QQQ | DFE + 网格 | 0.87 | 1.23 | +298% | +543% |
| IWM | 固定 + 网格 | 0.47 | 0.84 | +174% | +145% |
| XLK | DFE + 网格 | 0.94 | 1.17 | +237% | +781% |

## 文档

- [model-guide.zh.md](docs/model-guide.zh.md)
- [cycle-math.zh.md](docs/cycle-math.zh.md)
- [backtest-report.zh.md](docs/backtest-report.zh.md)
- [improvement-roadmap.zh.md](docs/improvement-roadmap.zh.md)

英文版是同目录去掉 `.zh` 的文件名。

## 参考

Achelis, S. B. (2001). *Technical analysis from A to Z* (2nd ed.). McGraw-Hill. (ISBN 978-0-07-136348-8)

Carter, J. F. (2005). *Mastering the trade: Proven techniques for profiting from intraday and swing trading setups*. McGraw-Hill. (ISBN 978-0-07-145958-7) 

DeMark, T. R. (1994). *The new science of technical analysis*. John Wiley & Sons. (ISBN 978-0-471-03548-0) 

Hurst, J. M. (1970). *The profit magic of stock transaction timing*. Prentice-Hall. (ISBN 978-0-13-095075-8)

Seban, O. (2009). *Tout le monde mérite d'être riche* (2nd ed.). Maxima. (ISBN 978-2-84001-618-2)

Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power spectra: A method based on time averaging over short, modified periodograms. *IEEE Transactions on Audio and Electroacoustics, 15*(2), 70–73. https://doi.org/10.1109/TAU.1967.1161901

Wilder, J. W., Jr. (1978). *New concepts in technical trading systems*. Trend Research. (ISBN 978-0-89459-027-6)

非投资建议。回测省略实盘摩擦，且容易过拟合。

## License

MIT，见 [LICENSE](LICENSE)。
