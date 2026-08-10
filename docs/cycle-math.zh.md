# 周期估计

本节单独说明图中 Cycle 周期长度（以交易日计）的估计流程：去趋势、频谱挑峰、手工/DFE/兜底三种来源，以及这些周期如何进入谐波拟合。完整流水线与交易决策见 [model-guide.zh.md](model-guide.zh.md)。

对应代码：`cycle_engine.py` 中的 `detrend_series`、`extract_dominant_periods`、`resolve_periods`、`resolve_cycle_config`、`build_overlay`。

## 1. 「周期」在本项目里指什么

这里的周期 **不是** 自然月、财报季之类的日历概念，而是：

> 在去掉长期趋势之后，价格残差里反复出现的、用「多少根日 K / 多少个交易日」度量的主导振荡长度。

例如输出：

```text
Cycle periods: [227.3, 126.8, 78.1] d  (source: dfe)
```

表示引擎认为当前样本里最主要的三个振荡大约是 **227 / 127 / 78 个交易日** 一圈（小数来自频谱分辨率，不是必须整到整数）。

之后每个周期 \(P\) 会拟合成：

\[
r(t) \approx A\sin\frac{2\pi t}{P} + B\cos\frac{2\pi t}{P}
\]

多个 \(P\) 叠加成粉色 Cycle 线，并外推成虚线 Projection。

---

## 2. 三种来源：手动 / DFE / 兜底

| `source`（日志字段） | 何时出现 | 周期从哪来 |
|----------------------|----------|------------|
| `manual` | 关掉「Auto-detect cycle periods」，手填 P1/P2/P3 | 用户输入的交易日长度 |
| `dfe` | 勾选 Auto DFE，且频谱挑峰成功 | `extract_dominant_periods` 从 PSD 峰选出 |
| `fallback` | Auto DFE 开着，但样本太短 / 无有效峰 / 补不齐 3 个 | 退回默认 `[127.0, 227.0, 78.0]` |

默认三周期常量：

```python
DEFAULT_PERIODS = [127.0, 227.0, 78.0]
```

UI 关掉 Auto 时，侧边栏 P1/P2/P3 的初值也是这三个；可改成任意正数（单位：交易日）。

---

## 3. 计算前必须做：去趋势

价格本身有涨跌斜坡。斜坡在频谱里会冒充「超长周期」。所以**先去趋势，再谈周期**。

```text
价格 close
    │
    ▼  detrend_series(degree=2)   # 默认二次多项式
趋势 trend  +  残差 residual = close − trend
    │
    └── 只把 residual 交给 DFE / 谐波拟合
```

要点：

- 时间轴用 bar 下标 `t = 0, 1, 2, …`（一根日 K = 1 个时间单位）
- 默认多项式次数 `DEFAULT_TREND_DEGREE = 2`
- 次数会被夹在 `1 … min(3, n-1)`，样本极少时降为一次

**周期是残差上的周期，不是原始收盘价曲线的周期。**

---

## 4. 实际拿哪一段残差来算周期？

即使下载了 700–900 根，DFE 与拟合默认只看**最近一段窗口**：

```python
DEFAULT_SLIDING_WINDOW = 252   # 约一年交易日
fit_residual = residual[-252:] # 更短则用全部
```

含义：

- 周期反映的是**近一年左右**主导节奏，而不是十年前的旧节奏  
- lookback 拉得很长，主要是为了指标稳定和 auto lookback 扫描；**真正定周期的仍是这 252 根残差**（除非总长度 < 252）

---

## 5. DFE：周期长度的自动算法

函数：`extract_dominant_periods(residual, n_periods=3, …)`  
中文名：**动态频率提取（Dynamic Frequency Extraction）**。

### 5.1 总览

```text
残差 x（已减均值）
    │
    ▼  scipy.signal.periodogram  →  (频率 f, 功率 PSD)
    │
    ▼  周期 P = 1 / f   （单位：交易日）
    │
    ▼  只保留  15 ≤ P ≤ n/2.5
    │
    ▼  在 PSD 上 find_peaks（显著性 ≥ 最大功率的 5%）
    │
    ▼  按功率从高到低贪心挑选：
         · 与已选周期相差 ≥ 10 天
         · 不是已选周期的 2× / ½× / 3× / ⅓× 谐波
         · 最多 3 个
    │
    ▼  不够 3 个 → 用 DEFAULT_PERIODS 补；仍不够 → 整组 fallback
    │
    ▼  按周期从长到短排序输出
```

### 5.2 为什么用 Periodogram？

Periodogram 估计「每个频率上能量有多大」。  
能量大的频率 \(f\)，对应振荡周期：

\[
P = \frac{1}{f}
\]

因为采样是「每个交易日一个点」、`fs=1.0`，所以：

- \(f = 1/20\) → \(P = 20\) 个交易日  
- \(f = 1/127\) → \(P = 127\) 个交易日  

**引擎报出的周期天数，本质上就是 PSD 峰值对应的 \(1/f\)。**

### 5.3 合法周期范围

| 约束 | 默认 | 原因 |
|------|------|------|
| 最短 `DFE_MIN_PERIOD` | 15 天 | 滤掉几天级噪声尖峰 |
| 最长 `max_period` | `n / 2.5` | 窗口太短时，禁止声称存在「比样本还离谱」的超长周期 |
| 样本下限 | `n ≥ 2 × min_period`（即至少约 30 根） | 太短则直接 fallback |

例：`n = 252` → 最长约 `252/2.5 ≈ 100.8` 天？  
注意：这里的 `n` 是**送进 DFE 的残差长度**。若用满 252 根，最长约 100 天——但默认兜底里有 227。  

实际运行中：

- Auto lookback 时，先在更长下载窗口上抽一次周期（可能 `n` 远大于 252）  
- 切片到最终 lookback 后，DFE 仍默认只取最近 252 根做第二次抽取  

因此「窗口长度」和「最长可检测周期」绑在一起：  
**送进 DFE 的序列越短，能稳定检测到的最长周期越短。**  
若第二次 DFE 在 252 根上找不到够长的峰，可能更多依赖默认/补齐逻辑。

### 5.4 如何从 PSD 上「找峰」

```python
prominence = max(psd.max() * 0.05, 1e-12)   # DFE_PROMINENCE_FRAC
peak_idx, _ = find_peaks(psd, prominence=prominence)
```

- 只保留相对最高峰「够突出」的局部峰（至少 5% 量级）  
- 再按该峰处的 PSD 值从大到小排序 → **能量最强的振荡优先入选**

若一个峰都没有 → `fallback`。

### 5.5 贪心筛选规则（避免选出「假的三个」）

对排序后的候选周期 \(p\)，依次尝试加入 `chosen`：

#### 规则 A — 最小间隔

```text
若存在已选 c，使 |p − c| < 10（DFE_MIN_SEP_DAYS）
  → 丢弃 p
```

防止 78 天和 80 天这种几乎重复的峰各占一个名额。

#### 规则 B — 谐波剔除 `_is_harmonic`

若 \(p\) 相对某个已选周期 \(e\)，接近下面任一关系（相对误差 `< 8\%`）：

| 关系 | 含义 |
|------|------|
| \(p \approx 2e\) | 二倍周期（半频） |
| \(p \approx e/2\) | 二分之一周期（倍频） |
| \(p \approx 3e\) | 三倍 |
| \(p \approx e/3\) | 三分之一 |

则丢弃 \(p\)。

目的：同一基频的倍频/分频不要占满 3 个槽位；希望留下**相对独立**的主导长度。

#### 规则 C — 名额

选满 `n_periods=3` 就停止。

### 5.6 补齐与 fallback

1. 若挑到的不足 3 个：按顺序尝试把 `DEFAULT_PERIODS` 里的 127、227、78 加进去（同样过间隔与谐波检查）  
2. 若仍不足 3 个：直接返回 `DEFAULT_PERIODS` 的前 `n_periods` 个，并设 `used_fallback=True`  
3. 最终 `chosen.sort(reverse=True)`：**长周期排前面**（例如 227, 127, 78）

`resolve_periods` 把 `used_fallback` 映射成日志里的 `source: fallback` 或 `source: dfe`。

### 5.7 DFE 参数速查

| 常量 | 值 | 作用 |
|------|-----|------|
| `DFE_MIN_PERIOD` | 15.0 | 最短周期（交易日） |
| `DFE_MIN_SEP_DAYS` | 10.0 | 两周期最小间隔 |
| `DFE_PROMINENCE_FRAC` | 0.05 | 峰显著性相对阈值 |
| `DFE_HARMONIC_TOL` | 0.08 | 谐波判定容差 |
| `n_periods` | 3 | 最多输出几个周期 |
| `DEFAULT_PERIODS` | [127, 227, 78] | 失败/补齐用的经验默认 |

---

## 6. 在整条流水线里，周期被算几次？

`resolve_cycle_config` 在 Auto DFE 打开时可能算 **两次**：

```text
① 下载完成后、切片前
   resolve_periods(全量 close 的残差窗口)
   → 得到一组 periods，用来算：
        min_lookback = max(678, ceil(3 × 最长周期))

② 若开启 auto lookback：按稳定性扫描选出 lookback，切出最近 L 根

③ 切片后再次（Auto DFE 仍开着时）
   resolve_periods(切好的 close)
   → 界面与拟合最终使用的 periods 以这次为准
```

原因简述：

- 第一次：先知道「最长周期大概多长」，才能定「至少要多少根历史」  
- 第二次：最终样本变了，频谱可能略变，**以切好窗口上的结果为准**

手动模式：不跑 DFE，全程用你填的 P1/P2/P3。

---

## 7. 周期定下来之后，怎么「用」这些数字？

选出的 `[P1, P2, P3]` 进入 `build_overlay`：

1. 再对（通常最近 252 根）残差做加权最小二乘，估每个 \(P\) 的 \(A,B\)  
2. 算 strength / phase / R²  
3. 把各分量叠加，缩放到价格坐标 → Cycle 实线  
4. 用同一组 \(A,B\) 往未来推 `future_days`（默认 65）根交易日 → Projection 虚线  

注意区分：

| 概念 | 是什么 | 不是什么 |
|------|--------|----------|
| **周期长度 P** | 「多久振荡一圈」（交易日） | 买卖点日期 |
| **相位 / 投影峰谷** | 在这一圈里现在走到哪、虚线何时拐 | 保证的价格顶底 |
| **强度 strength** | 该分量相对残差波动有多大 | 胜率 |

周期长度由 DFE（或手动）决定；**转折日**是拟合之后再解峰谷得到的，见主文档第 7 节。

---

## 8. 和 lookback 的关系（容易混淆）

| 问题 | 答案 |
|------|------|
| lookback 是不是周期？ | **不是**。lookback = 用多少根历史 K 线做整次分析 |
| 周期会不会影响 lookback？ | **会**。auto 模式下最少 lookback ≈ `max(678, 3×最长P)` |
| lookback 会不会影响周期？ | **会**。切窗后再跑一次 DFE，结果可能变 |
| 默认 252 窗口是什么？ | 在 lookback 内部，再截最近 252 根做 DFE/拟合 |

经验规则「至少 3 圈」：

```python
compute_min_lookback(periods) = max(678, ceil(3 * max(periods)))
```

例如最长 \(P=227\) → \(3×227=681\) → 至少约 681 根。

---

## 9. 数值例子（帮助建立直觉）

假设最近 252 根去趋势残差的 PSD 上，最强峰大致在：

- \(f_1 \approx 1/78\) → 候选 78 天  
- \(f_2 \approx 1/127\) → 候选 127 天  
- \(f_3 \approx 1/39\) → 约 39 天，但 ≈ \(78/2\)，被谐波规则丢掉  
- \(f_4 \approx 1/226\) → 候选 226 天  

间隔都 ≥ 10，且 226 与 127、78 不构成 2/3 倍关系 → 输出排序后类似：

```text
[226.x, 127.x, 78.x]   source: dfe
```

若全是杂峰、一个合格峰都没有：

```text
[227.0, 127.0, 78.0]   source: fallback
```

若你关掉 Auto，手填 `54, 108, 162`：

```text
[54.0, 108.0, 162.0]   source: manual
```

（日志里通常按引擎返回顺序打印；手动列表顺序以你输入为准。）

---

## 10. 读日志时怎么判断「周期算得靠不靠谱」

1. **`source: dfe`** — 频谱里真的挑到了峰；比 fallback 更「数据驱动」  
2. **`source: fallback`** — 频谱不可用，在用经验默认；周期数字别过度解读  
3. **`source: manual`** — 完全是你的假设，引擎只负责拟合，不负责「找对不对」  
4. **`Fit R²`** — 这组周期叠在一起能解释多少残差；很低说明「周期长度可能对、也可能只是噪声」  
5. **Warning: lookback < 3× longest period** — 历史相对最长周期偏短，长度估计与拟合都更不稳  

---

## 11. 想改「周期怎么算」时改哪里

| 你想改的行为 | 改什么 |
|--------------|--------|
| 默认三个兜底周期 | `DEFAULT_PERIODS` |
| 最短可检测周期 / 峰间隔 / 谐波容差 | `DFE_MIN_*`、`DFE_HARMONIC_TOL`、`DFE_PROMINENCE_FRAC` |
| 用近几年还是近半年做频谱 | `DEFAULT_SLIDING_WINDOW` |
| 去趋势用一次还是二次曲线 | `DEFAULT_TREND_DEGREE` |
| 一次分析用几个周期 | `extract_dominant_periods(..., n_periods=)` |
| 界面手填 vs 自动 | Streamlit「Auto-detect cycle periods」+ P1/P2/P3 |

---

## 12. 一句话总结

> **周期天数 =（可选）对近端去趋势残差做 periodogram，取功率峰对应的 \(1/f\)，去掉过近与谐波重复后最多留 3 个；失败则用 127/227/78；手动模式则完全用你填的交易日长度。**  
> 这些长度再进入 sin/cos 拟合，变成图上的 Cycle / Projection——**长度是「多久一圈」，不是「哪天买卖」。**

---

*对应代码：`cycle_engine.py` → `extract_dominant_periods` / `resolve_periods` / `resolve_cycle_config` / `build_overlay`。*
