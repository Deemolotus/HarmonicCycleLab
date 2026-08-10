# Cycle Estimation

This note explains how HarmonicCycleLab obtains the cycle lengths shown on the chart (in **trading days**): detrending, spectral peak picking, the three period sources (manual / DFE / fallback), and how those periods enter the harmonic fit. For the full pipeline and trade-state logic, see [model-guide.md](model-guide.md).

Code: `cycle_engine.py` — `detrend_series`, `extract_dominant_periods`, `resolve_periods`, `resolve_cycle_config`, `build_overlay`.

## 1. What “period” means here

A period is **not** a calendar month or earnings season. It is the dominant oscillation length, measured in daily bars, that remains after a long-run trend has been removed from price.

Example log line:

```text
Cycle periods: [227.3, 126.8, 78.1] d  (source: dfe)
```

The engine treats the leading oscillations as about 227 / 127 / 78 sessions per cycle. Fractional values come from spectral resolution; they need not be integers.

Each period \(P\) is fit as

\[
r(t) \approx A\sin\frac{2\pi t}{P} + B\cos\frac{2\pi t}{P}
\]

Components are summed into the Cycle overlay and extrapolated as the dashed Projection.

## 2. Sources: manual / DFE / fallback

| `source` | When | Origin |
|---|---|---|
| `manual` | Auto-detect off; P1/P2/P3 entered by hand | User trading-day lengths |
| `dfe` | Auto DFE on and peaks accepted | `extract_dominant_periods` on the PSD |
| `fallback` | Auto DFE on, but sample too short / no peaks / cannot fill three | Defaults `[127.0, 227.0, 78.0]` |

```python
DEFAULT_PERIODS = [127.0, 227.0, 78.0]
```

## 3. Detrend before anything else

A raw price slope leaks into the spectrum as a fake ultra-long cycle. The engine fits a low-order polynomial trend (default degree 2), then runs DFE and harmonic fitting on the **residual** only.

## 4. Which residual window?

Even if many bars are downloaded, period detection and fitting focus on a recent window (default `DEFAULT_SLIDING_WINDOW = 252` trading days). Longer lookbacks mainly stabilize indicators and auto-lookback scans; the rhythmic estimate still reflects recent structure unless the series is shorter than 252.

## 5. DFE (Dynamic Frequency Extraction)

On the fit residual, `scipy.signal.periodogram` yields a power spectrum. Peaks are filtered by minimum/maximum period, prominence, separation, and a simple harmonic check, then the top lengths are kept. If extraction fails, the code falls back to `DEFAULT_PERIODS`.

Implementation details, constants (`DFE_MIN_PERIOD`, prominence fraction, etc.), and lookback interaction are spelled out in the Chinese companion [cycle-math.zh.md](cycle-math.zh.md), which tracks the code line-by-line.

## 6. Into the fit

Resolved periods are passed to `build_overlay` / `metrics_for_window`: weighted least squares for each sinusoid on the recent residual, composite reconstruction, scaling onto the price pane for display, and forward projection for `future_days` sessions.

**Important:** the pink line scaled onto price is a **phase visualization**, not a dollar price target. See the labeling guidance in [improvement-roadmap.md](improvement-roadmap.md).
