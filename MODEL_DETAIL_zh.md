# CycleAnalysis — 模型与引擎详解

本文档面向希望**彻底理解主代码如何工作**的读者，覆盖端到端运行流程、周期（Cycle）如何选取、**DFE（Dynamic Frequency Extraction，动态频率提取）**原理与参数、谐波拟合与未来投影、各技术指标，以及最终量化决策如何综合这些信号。

> 主代码：`quant_engine.py`（量化引擎）+ `streamlit_app.py`（Web 入口）  
> 简称说明：界面与注释里写的是 **DFE**；口语里有时会说成 “DEF”，指的是同一件事。  
> **只关心「周期天数怎么算」：** 见专文 [CYCLE_CALCULATION_zh.md](CYCLE_CALCULATION_zh.md)。

---

## 1. 项目在做什么

本工具不是单纯画 K 线，而是把以下几块叠在同一张图上，并输出一段中文「量化决策」文字：

| 模块 | 作用（一句话） |
|------|----------------|
| **Cycle 谐波周期** | 从价格残差里找出主导周期长度，用正弦/余弦拟合，画出历史拟合线 + 未来虚线投影 |
| **SuperTrend** | 用 ATR 构造趋势带，判断当前偏多还是偏空，并给出防守价 |
| **TD Sequential** | DeMark 序列：TD9 Setup、TD13/15 Countdown，标极值与耗尽信号 |
| **Squeeze Momentum** | LazyBear 挤压动量：柱状动能 + 黑/灰/蓝点表示挤压状态 |
| **CMF** | Chaikin Money Flow：近 N 日资金流入/流出 |

核心哲学可以概括为：

1. **趋势定方向**（SuperTrend 右侧/左侧）  
2. **周期定相位**（现在处在周期的上升段还是下降段、大概何时见顶/见底）  
3. **TD / SQZ / CMF 定时机与确认**（极值、动能、资金是否共振）

---

## 2. 文件与职责

```
CycleAnalysis-main/
├── streamlit_app.py      # UI：参数 → 调引擎 → 画图 + 日志
├── quant_engine.py       # 真正的模型与指标（无 GUI）
├── nya_V6_backup.py      # 原桌面版备份，不参与 Web 运行
├── requirements.txt
└── MODEL_DETAIL_zh.md    # 本文件
```

### 2.1 `streamlit_app.py` 做什么

1. 侧边栏收集参数（`AnalysisParams`）  
2. 用户点击 **▶ Run & Analyze** 后调用 `run_analysis()`  
3. `run_analysis()` 只负责**编排流水线**：下载数据 → `resolve_cycle_config` → `metrics_for_window` → 算各指标 → `analyze_trade_state` → `build_plotly_chart`  
4. 把 Plotly 图、引擎日志、检测到的周期展示出来，并提供 HTML 下载  

**数学与策略逻辑全部在 `quant_engine.py`，改模型优先改引擎文件。**

### 2.2 `quant_engine.py` 模块地图

| 区块 | 主要函数 | 内容 |
|------|----------|------|
| 指标 | `chaikin_money_flow`, `calculate_supertrend`, `td_sequential`, `squeeze_momentum` | 经典技术指标 |
| 数据 | `download_ohlcv`, `DataFetchError` | yfinance 拉 OHLCV |
| 周期核心 | `detrend_series`, `build_overlay`, `metrics_for_window`, `extract_dominant_periods`, `resolve_periods`, `choose_lookback_bars`, `resolve_cycle_config` | DFE、拟合、投影、lookback |
| 决策 | `describe_cycle_outlook`, `analyze_trade_state` | 中文交易状态报告 |
| 图表 | `build_plotly_chart` | Plotly 多子图 |

---

## 3. 端到端运行流程（一次点击之后发生了什么）

下面按 `run_analysis()` 的真实顺序说明。

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. 解析时间窗口                                                  │
│    · 填了 Start Date → 用该区间下载                              │
│    · 只填 Lookback Bars → 从 End Date 往前推 N 个交易日          │
│    · 两者都空 → Auto lookback：先拉最多 MAX_LOOKBACK(900) 根     │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. download_ohlcv(symbol, start, end)                            │
│    Yahoo Finance → Close / High / Low / Volume                   │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. resolve_cycle_config(...)                                     │
│    A. 若 Auto DFE：在当前窗口上第一次抽周期                       │
│    B. 若 Auto lookback：按「稳定性扫描」选最优 lookback 长度      │
│    C. 按 lookback 切出最近 N 根 bar                               │
│    D. 若 Auto DFE：在切好的窗口上再抽一次周期（最终采用）         │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. metrics_for_window(close, periods, future_days)               │
│    去趋势 → 加权最小二乘拟合 sin/cos → 合成曲线 → 缩放到价格     │
│    → 未来投影 → 相位分 / R² / 转折日报告                         │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. 并行计算技术指标                                              │
│    SuperTrend / TD Sequential / Squeeze / CMF                    │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. analyze_trade_state(...)                                      │
│    趋势 + TD + SQZ + CMF + 周期方向 → 中文决策文案                 │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. build_plotly_chart(...)                                       │
│    主图：价格 + Cycle(实线) + Projection(虚线) + ST + TD          │
│    副图：SQZ（可选）+ CMF                                        │
└─────────────────────────────────────────────────────────────────┘
```

### 3.1 时间窗口三种模式（UI 侧）

| UI 输入 | 行为 |
|---------|------|
| **Start Date 非空** | 按起止日期下载；`auto_lookback=False`；若未再指定 lookback，则用整段下载数据 |
| **Start Date 空，Lookback Bars 有值** | `explicit_lookback = N`；start ≈ end 往前 N 个交易日 |
| **Start Date 与 Lookback 都空** | `auto_lookback=True`；先下载最多约 900 根，再由引擎扫描选出最终 lookback（约 678–900） |

默认 End Date = 今天；默认 Future Projection = **65** 个交易日（虚线向前画多远）。

---

## 4. 核心常量（读代码时先记住这些）

文件顶部（`quant_engine.py`）：

| 常量 | 默认值 | 含义 |
|------|--------|------|
| `DEFAULT_SYMBOL` | `"HON"` | 默认标的 |
| `MIN_LOOKBACK_BARS` | `678` | 自动 lookback 下限；也是「建议最少历史长度」 |
| `MAX_LOOKBACK_BARS` | `900` | 自动 lookback / 首次拉取上限 |
| `LOOKBACK_STEP` | `10` | 稳定性扫描步长（每 10 根试一次） |
| `DEFAULT_FUTURE_DAYS` | `65` | 未来投影交易日数 |
| `DEFAULT_PERIODS` | `[127, 227, 78]` | DFE 失败时的兜底周期（交易日） |
| `PHASING_SCALE` | `209` | 把相位位置映射成整数「相位分」的缩放 |
| `DEFAULT_SLIDING_WINDOW` | `252` | 拟合与 DFE 默认只用**最近约 1 年**（252 交易日） |
| `DEFAULT_TREND_DEGREE` | `2` | 去趋势多项式次数（二次趋势） |
| `WINDOW_MIN_WEIGHT` | `0.35` | 拟合时最旧样本权重下限 |
| `WINDOW_WEIGHT_POWER` | `1.35` | 权重曲线幂次（越近权重越大） |
| `ROBUST_SIGMA_FACTOR` | `1.4826` | MAD → 稳健标准差（近似正态）的系数 |

**重要设计点：**  
即使 lookback 有 700–900 根，**真正做 DFE 与谐波拟合时，默认只看最近 `sliding_window=252` 根**的去趋势残差。更早的历史主要用于保证指标稳定、以及 auto lookback 扫描时对比「加长历史会不会改结论」。

---

## 5. 什么是 DFE（Dynamic Frequency Extraction）

### 5.1 一句话定义

**DFE = 对「去趋势后的价格残差」做功率谱密度（PSD / periodogram），找出能量最高、彼此不太像谐波倍频的若干个周期长度（单位：交易日）。**

对应函数：`extract_dominant_periods()`，由 `resolve_periods()` 调用。

### 5.2 为什么要先去趋势

价格本身有长期上涨/下跌趋势。若不去掉趋势，频谱会被低频「假周期」污染（看起来像超长周期，其实只是斜坡）。

`detrend_series(values, degree=2)`：

1. 用时间下标 `t = 0,1,2,…` 对价格做 **degree 次多项式拟合**（默认二次）  
2. `residual = price - trend`  
3. 后续频谱与谐波拟合都在 **residual** 上进行  

次数限制在 1–3，且不超过 `len(values)-1`，避免样本太少时过拟合。

### 5.3 DFE 算法逐步拆解

输入：残差序列 `residual`（通常再切成最近 252 根）  
输出：`periods`（最多 3 个，从大到小排序）+ `used_fallback`（是否用了兜底）

#### Step A — 样本是否够长

```
若 n < 2 * DFE_MIN_PERIOD（默认 15 → 即 n < 30）
  → 直接返回 DEFAULT_PERIODS，used_fallback=True
```

#### Step B — Periodogram（周期图）

```python
freqs, psd = periodogram(x, fs=1.0, detrend=False)
periods = 1.0 / freqs   # 频率 → 周期（交易日）
```

- `fs=1.0`：每个 bar 为单位时间，因此周期单位就是「多少根 K 线 / 多少交易日」  
- 去掉 `freqs == 0`（直流）  
- 只保留周期落在  
  - `min_period = 15` 天以上  
  - `max_period = n / 2.5` 以下（避免窗口太短却声称存在极长周期）

#### Step C — 在 PSD 上找峰

```python
prominence = max(psd.max() * 0.05, 1e-12)   # DFE_PROMINENCE_FRAC = 0.05
peak_idx = find_peaks(psd, prominence=prom)
```

峰值按 PSD 能量从高到低排序。

#### Step D — 贪心挑选，避免「挤在一起」和「谐波重复」

对每个候选周期 `p`：

1. **最小间隔**：与已选周期相差小于 `DFE_MIN_SEP_DAYS = 10` → 丢弃  
2. **谐波过滤** `_is_harmonic`：若 `p` 约等于已选周期的 `2×、½×、3×、⅓×`（相对误差 `< DFE_HARMONIC_TOL=0.08`）→ 丢弃  
   - 目的：同一基频的倍频/分频不要占满 3 个名额  
3. 选满 `n_periods=3` 个就停  

#### Step E — 不够 3 个时用默认周期补齐

按 `DEFAULT_PERIODS = [127, 227, 78]` 依次尝试加入（同样过间隔与谐波检查）。  
若仍不够 → 整组退回默认，并标记 `fallback`。

#### Step F — 排序输出

`chosen.sort(reverse=True)`：周期从长到短（例如 `227, 127, 78`）。

### 5.4 `resolve_periods`：DFE vs 手动

```text
auto=True（UI 勾选 Auto-detect cycle periods）
  → detrend → 取 sliding_window 切片 → extract_dominant_periods
  → source = "dfe" 或 "fallback"

auto=False 且用户填了 P1/P2/P3
  → 直接用手动列表，source = "manual"

都没有
  → DEFAULT_PERIODS，source = "manual"（在 resolve_cycle_config 分支）
```

日志里会看到类似：

```text
Cycle periods: [227.3, 126.8, 78.1] d  (source: dfe)  lookback: 720 bars
```

或 `source: fallback` / `source: manual`。

### 5.5 DFE 相关参数一览

| 参数 | 值 | 作用 |
|------|-----|------|
| `DFE_MIN_PERIOD` | 15 | 最短可接受周期（过滤噪声高频） |
| `DFE_MIN_SEP_DAYS` | 10 | 两个周期至少相差这么多天 |
| `DFE_PROMINENCE_FRAC` | 0.05 | 峰显著性：至少是最大 PSD 的 5% |
| `DFE_HARMONIC_TOL` | 0.08 | 判定倍频/分频的相对容差 |
| `n_periods` | 3 | 最多选几个主导周期 |
| `max_period` | `n/2.5` | 最长周期上限（随窗口变） |

### 5.6 DFE 的局限（读结果时必须知道）

- 周期是**统计主导频率**，不是物理定律；换标的、换窗口会变。  
- 谐波过滤会丢掉「看起来像倍频」的峰，有时真实市场确实存在谐波关系。  
- `fallback` 意味着频谱里没找到可靠峰，系统在用经验默认值 `[127, 227, 78]`。  
- 拟合与投影都是**去趋势残差上的正弦模型**，再缩放到价格刻度——**不是价格预测器**，只是相位示意。

---

## 6. Lookback（回看长度）怎么选

### 6.1 `compute_min_lookback(periods)`

```text
min_lookback = max(MIN_LOOKBACK_BARS, ceil(3 × 最长周期))
```

例如最长周期 227 天 → `3×227 = 681`，再与 678 取 max → 至少约 681 根。  
直觉：**至少要覆盖最长周期大约 3 圈**，拟合才相对稳。

### 6.2 Auto lookback：`choose_lookback_bars`（稳定性扫描）

目标：在「够长」的前提下，**尽量用更长的历史**，但一旦加长后关键结论开始漂，就停在上一个稳定点。

流程：

1. 从 `min_bars` 切出数据，算一组基准指标：  
   - 周期强度排序 `rank`（按 strength）  
   - `p_score`（相位分）  
   - `combined_r2`  
   - `top_strength`（最强周期的 robust_strength）  
2. 从 `min_bars + 10` 一直试到 `max_bars`（默认最多 900），步长 10：  
   - 每次重新 `metrics_for_window`  
   - **若同时满足**：  
     - `rank` 与基准完全相同  
     - `|top_strength - base| ≤ 0.02`  
     - `|R² - base| ≤ 0.01`  
     - `|p_score - base| ≤ 5`  
     → 认为仍然稳定，`chosen = 当前 lb`  
   - **一旦任一条件破坏** → `break`，不再加长  
3. 返回 `chosen`

因此最终 lookback 往往是「从最短够用窗口往上扩，直到结论开始敏感」的那个长度。

### 6.3 `resolve_cycle_config` 里的两次 DFE

这是容易忽略的细节：

```text
若 auto_dfe:
  ① 在「全量已下载数据」上先抽一次周期（给 auto lookback 算 min_bars 用）

若 auto_lookback:
  扫描选 lookback，并切片

切片之后，若 auto_dfe:
  ② 在「最终 lookback 窗口」上再抽一次周期  ← 界面上最终显示的是这次
```

原因：先用大致周期决定最少需要多少 bar；切完窗口后频谱可能略变，所以再抽一次更贴合最终样本。

### 6.4 手动 lookback / 起止日期

- `explicit_lookback=N`：直接 `min(N, len(close))`  
- 未指定 lookback 且非 auto：用全部已下载数据  
- 若最终 `lookback < 3×最长周期`，日志会打 **Warning**（仍继续跑，但提示不稳定风险）

---

## 7. 谐波拟合与 Cycle 曲线（模型本体）

主函数：`build_overlay(close, periods, future_days, sliding_window=252, trend_degree=2)`

### 7.1 几何图像

对每个周期 \(P\)，在去趋势残差上拟合：

\[
r(t) \approx A\sin(2\pi t / P) + B\cos(2\pi t / P)
\]

多个周期线性叠加成 composite residual，再**按价格分位数缩放到价格坐标**，得到图上的粉色 Cycle 线；历史段实线，未来段虚线 Projection。

### 7.2 逐步计算

#### (1) 去趋势

对整段 `close`：`residual, trend = detrend_series(...)`。

#### (2) 拟合窗口

默认只取最近 `sliding_window` 根：

```text
fit_slice = close[-252:]   # 若总长度更短则用全部
```

#### (3) 近端加权（Weighted LS）

权重：

```text
w_i = linspace(0.35, 1.0, n) ** 1.35
```

越靠近「今天」权重越大。实际求解：

```text
对设计矩阵 D = [sin(2πt/P), cos(2πt/P)]
用 √w 加权后做 lstsq：  (D * √w) @ coef ≈ residual * √w
```

得到每个周期的系数 `coefficients[p] = [A, B]`。

#### (4) 单周期统计 `cycle_stats[p]`

| 字段 | 公式/含义 |
|------|-----------|
| `amp` | \(\sqrt{A^2+B^2}\) 振幅 |
| `strength` | `amp / std(残差)` |
| `robust_strength` | `amp / (1.4826 × MAD)`，对异常值更稳 |
| `phase_position` | 当前时刻该分量取值 `/ amp`，约在 \([-1,1]\)，近 0 表示接近零轴穿越，近 ±1 表示近峰/谷 |
| `effective_score` | `strength × (1 - |phase_position|)`：强且相位不极端时，排序更靠前 |

`ranked_periods` 按 **`effective_score`** 从高到低排（用于 timing 报告里的 Dominant / 2nd）。

#### (5) 联合 R²

在拟合窗口上：

\[
R^2 = 1 - \frac{\sum (r - \hat r)^2}{\sum (r - \bar r)^2}
\]

日志里的 `Fit R²=...`。R² 低（如 `< 0.35`）时，转折日只作粗糙参考。

#### (6) 相位分 `p_score`

取 strength 最强的两个周期，对其 `phase_position` 做加权平均，再乘 `PHASING_SCALE=209` 并四舍五入成整数。  
Auto lookback 用它判断「相位结论有没有漂」。

#### (7) 合成全长曲线并缩放

`compose_full_series`：在 `历史长度 + future_days` 的交易日索引上，把各周期 sin/cos 分量再叠加一遍（用已估系数外推）。

`scale_composite_to_price`：用价格与 composite 各自的 5%–95% 分位数做线性映射，把残差尺度拉回「看起来像价格」的刻度。  
因此：**纵轴上的投影高低不等于目标价**，只表示相位起伏的形状。

#### (8) 未来日历

`future_index = bdate_range(最后收盘日的下一交易日, periods=future_days)`  
虚线画在这些交易日上。

### 7.3 转折日估计

两套互补方法：

**A. 单分量解析解 `days_to_next_turn`**  
把 \(A\sin + B\cos\) 写成相位形式，解下一个峰（`kind=peak`）或谷（`kind=trough`）相对「现在」还有多少根 bar，再换成日历日。  
Timing 报告里 Dominant / 2nd 的 next trough/peak 来自这里。

**B. 合成线上找极值 `projection_extrema`**  
对虚线投影段做 `find_peaks` / `find_peaks(-y)`，标出合成线的峰谷（图上红三角谷、绿三角峰）。  
交易报告里「预计约 X 个交易日后见顶/见底」优先用合成线下一个极值。

文案明确写了：这些是**模型在去趋势周期上的转折**，不是保证的价格低点。

---

## 8. 各技术指标在引擎中的定义

### 8.1 SuperTrend

`calculate_supertrend(high, low, close, period=10, multiplier=3.0)`

1. True Range → ATR（`period` 日均）  
2. Basic Upper/Lower = HL2 ± multiplier×ATR  
3. Final 带按经典规则递推；趋势 `+1/-1` 在收盘穿越下轨/上轨时翻转  
4. 图上：多头绿带、空头红带  

决策里：`current_price > st_line` → 右侧偏多；否则偏空。防守线用当前 SuperTrend 线。

### 8.2 TD Sequential（DeMark）

`td_sequential(close, high, low, cd_target=13, cd_extended=15)`

**Setup（数到 9）**

- 收盘价 < 4 根前收盘 → Buy Setup 计数 +1（Sell 清零）  
- 收盘价 > 4 根前收盘 → Sell Setup 计数 +1  
- 到 9 → 发出 `buy9` / `sell9`  
- Perfect：Buy9 时最近两根低点 ≤ 前两根低点的更低者；Sell9 对称用高点  

**Countdown（Setup 完成后）**

- Buy CD：收盘 ≤ 2 根前最低价才计 1 个数；到 `cd_target`(13)、`cd_extended`(15) 发信号  
- Sell CD：收盘 ≥ 2 根前最高价才计数  
- 反向 Setup 完成会打断当前 CD  

返回：setup 数组、countdown 数组、`TDSignal` 列表（供画图与决策）。

### 8.3 Squeeze Momentum（LazyBear）

`squeeze_momentum(...)`

1. 布林带 BB（默认长度 20、倍数 2）与肯特纳通道 KC（长度 20、倍数 1.5×ATR 型 range）  
2. **挤压状态**  
   - `sqzOn`：BB 完全在 KC 内侧（黑点）  
   - `sqzOff`：BB 完全在 KC 外侧（灰点）  
   - `noSqz`：其它（蓝点）  
3. 动量值：对  
   `delta = close - ((最高+最低)/2 + MA)/2`  
   在 KC 窗口上做线性回归，取窗口末端拟合值作为柱高  
4. 柱色：绿/青（正且升/降）、红/深红（负且降/升）  

决策用最新柱相对前一根的升降与正负。

### 8.4 CMF（Chaikin Money Flow）

默认窗口 20：

\[
\text{MF Mult} = \frac{(C-L)-(H-C)}{H-L},\quad
\text{CMF} = \frac{\sum MF\times Vol}{\sum Vol}
\]

CMF > 0 → 文案写「流入(机构吸筹)」；否则「流出(机构派发)」。

---

## 9. 量化决策逻辑（`analyze_trade_state`）

输入：最新价、SuperTrend、近期 TD9、SQZ 柱、CMF、以及周期展望 `describe_cycle_outlook`。

### 9.1 周期展望 `describe_cycle_outlook`

对未来投影段做直线斜率：

- `slope_pct`：每交易日投影变动占现价百分比  
- `> +0.02%` → 方向 `up`；`< -0.02%` → `down`；否则 `flat`  
- 置信度：R²≥0.5 高；≥0.35 中；否则「低(仅参考)」  
- 附上下一个合成峰/谷的大致交易日数  

**再次强调：** 只表示周期相位方向，不是涨跌概率或目标价。

### 9.2 决策树（简化）

```
资金流向：先报 CMF

若 SuperTrend 偏多（右侧）：
  · 近 3 根内有 TD9 卖 → 禁止加仓、减仓锁利
  · 否则若 SQZ 柱上升且 >0：
      · CMF>0 且周期 up   → 正金字塔加仓（三重共振）
      · CMF>0 且周期 down → 可加但轻仓/分批
      · CMF≤0             → 顶背离风险，停止买入
  · 否则动能弱：
      · 周期 up → 回踩可低吸
      · 周期 down → 观望等周期见底
  · 止损：SuperTrend 支撑

若 SuperTrend 偏空：
  · 近 3 根内有 TD9 买：
      · 左侧极限 / 漏斗建仓；CMF>0 提示逆势吸筹
      · 周期 up → 共振，反弹概率增；周期 down → 可能逃命波
      · 极限止损 ≈ TD9 低点 − ATR(14)
  · 无 TD9 买：
      · 周期 up → 可自选观察，等转右侧
      · 否则空仓观望
```

决策文案追加在 Engine Output 日志末尾（`▼▼▼量化决策▼▼▼`）。

---

## 10. 图表如何对应模型

主图（Row 1）：

| 图层 | 含义 |
|------|------|
| 浅蓝价线 | 收盘价 |
| 粉实线 Cycle | 历史段谐波合成（已缩放到价格） |
| 粉虚线 Projection | 未来 `future_days` 外推 |
| 红/绿三角 | 投影段合成线的谷/峰 |
| SuperTrend 绿/红 | 趋势带 |
| TD 三角与数字 | Setup / Countdown |

副图：

| 行 | 内容 |
|----|------|
| SQZ（可选） | 动量柱 + 状态点 |
| CMF | 资金流，零轴上下 |

标题旁 `Top Strength`：所有周期里最大的 `robust_strength`。

---

## 11. 日志字段怎么读

一次成功运行，Engine Output 典型结构：

```text
Fetching Data for XXX...
  Downloaded N bars (start → end)
Auto-selecting lookback ...          # 仅 auto 模式
  Testing 688 bars…                  # 扫描过程
Cycle periods: [a, b, c] d  (source: dfe|fallback|manual)  lookback: L bars
Fit R²=0.xxxx  ranked=[...]
── Cycle timing (harmonic projection) ──
  Dominant ... → next trough/peak ...
  Composite line ...
▼▼▼量化决策▼▼▼
  资金流向 / 当前状态 / 动作 / 周期模型 ...
```

建议阅读顺序：

1. `source` 是不是 `dfe`（可信度高于纯 fallback）  
2. `R²` 是否过低  
3. timing 里 Dominant 下一转折  
4. 决策段是否与 ST + CMF + TD 一致  

---

## 12. 关键函数调用关系（速查）

```
streamlit_app.run_analysis
  ├─ download_ohlcv
  ├─ resolve_cycle_config
  │    ├─ resolve_periods → detrend_series → extract_dominant_periods
  │    ├─ compute_min_lookback
  │    ├─ choose_lookback_bars → metrics_for_window → build_overlay
  │    └─（切片后再）resolve_periods
  ├─ metrics_for_window
  │    └─ build_overlay
  │         ├─ detrend_series
  │         ├─ lstsq 拟合各周期
  │         ├─ compose_full_series + scale_composite_to_price
  │         └─（外）build_cycle_timing_report / projection_extrema
  ├─ calculate_supertrend / td_sequential / squeeze_momentum / chaikin_money_flow
  ├─ analyze_trade_state → describe_cycle_outlook
  └─ build_plotly_chart
```

---

## 13. 调参建议（实操向）

| 目的 | 建议 |
|------|------|
| 让系统自己找周期 | 勾选 Auto DFE；Start/Lookback 留空走 auto lookback |
| 研究某个固定周期假设 | 关掉 Auto DFE，手填 P1/P2/P3（如 78/127/227） |
| 加快调试 | 填固定 Lookback（如 700），避免 30–90 秒扫描 |
| 投影看得更远/更近 | 改 Future Projection（默认 65） |
| 不信周期时 | 看 R² 与 `source: fallback`；决策以 ST+CMF+TD 为主 |

修改引擎默认行为（窗口 252、最小周期 15、默认三周期等）直接改 `quant_engine.py` 顶部常量即可；UI 侧对应项在 `streamlit_app.build_sidebar`。

---

## 14. 与桌面版关系

- Web 引擎从 `nya_V6.py` 抽出，逻辑对齐；仓库内 `nya_V6_backup.py` 仅备份对照。  
- 改周期/指标：**优先改 `quant_engine.py`**。  
- 同仓库还有 `TDsearch-main/`：全市场 TD 扫描工具，**不是**本 Cycle 谐波引擎的一部分。

---

## 15. 免责声明（模型边界）

本系统输出的 Cycle 线、投影峰谷、相位方向与中文「动作」建议，均为**技术分析示意**，基于公开行情与启发式规则，**不构成投资建议**。DFE 找到的周期会随样本变化；谐波外推在趋势突变、事件冲击时会迅速失效。实盘请结合自身风控与更多信息源。

---

*文档对应代码版本：仓库内 `quant_engine.py` / `streamlit_app.py`（含 DFE）。*
