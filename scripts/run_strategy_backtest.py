#!/usr/bin/env python3
"""
Walk-forward multi-factor strategy backtest vs buy-and-hold.

走步进多因子策略回测，并与买入持有对比。

Score = w_td * TD + w_cycle * Cycle + w_cmf * CMF + w_st * SuperTrend
Position: long when score >= threshold, else cash (long-only).
仓位：得分不低于阈值则做多，否则持现金（只做多）。

Execution: signal on close[t], fill at next close[t+1] (no same-bar lookahead).
成交：t 收盘出信号，t+1 收盘成交（避免同根偷看）。

Cycle periods: fixed DEFAULT_PERIODS unless --use-dfe.
周期：默认固定 DEFAULT_PERIODS；加 --use-dfe 则每次刷新用 DFE。
"""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cycle_engine as qe

ROOT_OUT = Path(__file__).resolve().parents[1] / "tmp" / "backtest"
START = "2014-01-01"
END = None  # through today
WARMUP_BARS = 400
LOOKBACK_BARS = 505  # ~2y; enough for 252 fit window + default periods
CYCLE_REFRESH = 5  # recompute cycle every N bars (cost/accuracy tradeoff)
FUTURE_DAYS = 65
COST_BPS = 5.0  # round-trip approx per trade side → applied on turnover


@dataclass
class WeightSet:
    td: float
    cycle: float
    cmf: float
    st: float

    def normalized(self) -> "WeightSet":
        s = self.td + self.cycle + self.cmf + self.st
        if s <= 0:
            return WeightSet(0.25, 0.25, 0.25, 0.25)
        return WeightSet(self.td / s, self.cycle / s, self.cmf / s, self.st / s)


def download_symbol(
    symbol: str, start: str, end: str | None
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    end_d = end or pd.Timestamp.today().date().isoformat()
    return qe.download_ohlcv(symbol, start, end_d)


def td_score_series(close: pd.Series, high: pd.Series, low: pd.Series, half_life: int = 5) -> np.ndarray:
    """Decaying TD9 buy/sell score in [-1, 1]. buy9 → +, sell9 → −."""
    _, _, signals = qe.td_sequential(close, high, low)
    n = len(close)
    score = np.zeros(n, dtype=float)
    decay = np.log(2) / max(half_life, 1)
    for sig in signals:
        if sig.kind not in ("buy9", "sell9"):
            continue
        sign = 1.0 if sig.kind == "buy9" else -1.0
        for j in range(sig.idx, min(n, sig.idx + half_life * 4 + 1)):
            age = j - sig.idx
            score[j] += sign * np.exp(-decay * age)
    return np.clip(score, -1.0, 1.0)


def cmf_score_series(close, high, low, volume, n: int = 10) -> np.ndarray:
    cmf = qe.chaikin_money_flow(close, high, low, volume, n=n).fillna(0.0).values
    # squash to [-1, 1]
    return np.tanh(cmf * 8.0)


def st_score_series(high, low, close, period=10, mult=3.0) -> np.ndarray:
    trend, _ = qe.calculate_supertrend(high, low, close, period=period, multiplier=mult)
    return np.where(trend >= 0, 1.0, -1.0).astype(float)


def resolve_periods_for_window(close_window: pd.Series, use_dfe: bool) -> list[float]:
    """Causal period selection: fixed DEFAULT_PERIODS, or DFE on detrended residual."""
    if not use_dfe:
        return list(qe.DEFAULT_PERIODS)
    try:
        residual, _ = qe.detrend_series(close_window.values.astype(float))
        fit = residual[-min(len(residual), qe.DEFAULT_SLIDING_WINDOW) :]
        periods, _fallback = qe.extract_dominant_periods(fit, n_periods=3)
        return list(periods)
    except Exception:
        return list(qe.DEFAULT_PERIODS)


def cycle_score_at(close_window: pd.Series, use_dfe: bool = False) -> float:
    """
    Causal cycle score from projection slope + proximity to projected peak.
    +1 up / -1 down / 0 flat; reduced when near a projected peak within horizon.
    """
    if len(close_window) < 80:
        return 0.0
    periods = resolve_periods_for_window(close_window, use_dfe=use_dfe)
    try:
        m = qe.metrics_for_window(close_window, periods, FUTURE_DAYS)
        outlook = qe.describe_cycle_outlook(close_window, m)
    except Exception:
        return 0.0

    direction = outlook.get("direction", "flat")
    base = {"up": 1.0, "down": -1.0, "flat": 0.0}.get(direction, 0.0)

    # Soft veto near projected peak (user: TD buy but cycle near high → don't buy)
    days = outlook.get("next_turn_days")
    kind = outlook.get("next_turn_kind")
    if kind == "peak" and days is not None and days <= 15:
        base = min(base, 0.0) - 0.35 * max(0.0, 1.0 - days / 15.0)
    elif kind == "trough" and days is not None and days <= 15:
        base = max(base, 0.0) + 0.25 * max(0.0, 1.0 - days / 15.0)

    return float(np.clip(base, -1.0, 1.0))


def build_cycle_scores(
    close: pd.Series, warmup: int, lookback: int, refresh: int, use_dfe: bool = False
) -> np.ndarray:
    n = len(close)
    scores = np.full(n, np.nan)
    last = 0.0
    for i in range(warmup, n):
        if (i - warmup) % refresh == 0 or np.isnan(scores[i - 1] if i else np.nan):
            start = max(0, i + 1 - lookback)
            last = cycle_score_at(close.iloc[start : i + 1], use_dfe=use_dfe)
        scores[i] = last
    scores[:warmup] = 0.0
    return scores


def simulate(
    close: pd.Series,
    scores: dict[str, np.ndarray],
    weights: WeightSet,
    threshold: float,
    cost_bps: float = COST_BPS,
) -> dict:
    w = weights.normalized()
    n = len(close)
    combined = (
        w.td * scores["td"]
        + w.cycle * scores["cycle"]
        + w.cmf * scores["cmf"]
        + w.st * scores["st"]
    )
    # signal at t → position held from t+1 to t+2 close
    target = (combined >= threshold).astype(float)
    position = np.zeros(n)
    position[1:] = target[:-1]

    rets = close.pct_change().fillna(0.0).values
    strat_rets = position * rets
    turnover = np.abs(np.diff(position, prepend=0.0))
    costs = turnover * (cost_bps / 10000.0)
    strat_rets = strat_rets - costs

    equity = np.cumprod(1.0 + strat_rets)
    bh_equity = close / close.iloc[0]
    # Align all strategies to the same tradeable window for fair BH comparison
    start_i = WARMUP_BARS

    def _stats(eq: np.ndarray, r: np.ndarray, i0: int) -> dict:
        eq = eq[i0:]
        r = r[i0:]
        if len(eq) < 2:
            return {}
        total = float(eq[-1] / eq[0] - 1.0)
        years = max(len(eq) / 252.0, 1e-9)
        cagr = float((eq[-1] / eq[0]) ** (1 / years) - 1.0)
        vol = float(np.std(r, ddof=0) * np.sqrt(252))
        mu = float(np.mean(r) * 252)
        sharpe = float(mu / vol) if vol > 1e-12 else 0.0
        peak = np.maximum.accumulate(eq)
        dd = eq / peak - 1.0
        max_dd = float(dd.min())
        return {
            "total_return": total,
            "cagr": cagr,
            "vol": vol,
            "sharpe": sharpe,
            "max_dd": max_dd,
            "exposure": float(np.mean(position[i0:])),
            "n_trades": int(np.sum(turnover[i0:] > 0)),
        }

    bh_rets = rets.copy()
    return {
        "weights": asdict(w),
        "threshold": threshold,
        "strategy": _stats(equity, strat_rets, start_i),
        "buyhold": _stats(bh_equity.values.astype(float), bh_rets, start_i),
        "equity": equity,
        "bh_equity": bh_equity.values.astype(float),
        "position": position,
        "combined": combined,
        "dates": close.index,
        "start_i": start_i,
    }


def weight_grid(step: float = 0.1) -> list[WeightSet]:
    """Weights on simplex, summing to 1, step grid. Includes user's 35/45/10/10."""
    pts = np.arange(0.0, 1.0 + 1e-9, step)
    out: list[WeightSet] = []
    for td, cy, cm in itertools.product(pts, repeat=3):
        st = 1.0 - td - cy - cm
        if st < -1e-9 or st > 1.0 + 1e-9:
            continue
        st = max(0.0, round(st, 10))
        if abs(td + cy + cm + st - 1.0) > 1e-8:
            continue
        out.append(WeightSet(td, cy, cm, st))
    # always include suggested blend
    out.append(WeightSet(0.35, 0.45, 0.10, 0.10))
    # dedupe
    seen = set()
    uniq = []
    for w in out:
        key = (round(w.td, 4), round(w.cycle, 4), round(w.cmf, 4), round(w.st, 4))
        if key not in seen:
            seen.add(key)
            uniq.append(w)
    return uniq


def run_backtest(
    symbol: str,
    out_dir: Path | None = None,
    *,
    use_dfe: bool = False,
    cycle_only: bool = False,
    tag: str | None = None,
) -> dict:
    mode = "cycle_only" if cycle_only else "grid"
    period_src = "dfe" if use_dfe else "fixed"
    label = tag or f"{period_src}_{mode}"
    out_dir = out_dir or (ROOT_OUT / label / symbol.upper())
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n==== {symbol.upper()} | periods={period_src} | mode={mode} ====")
    print(f"Downloading {symbol} {START} → …")
    close, high, low, volume = download_symbol(symbol, START, END)
    df = pd.concat([close, high, low, volume], axis=1, keys=["c", "h", "l", "v"]).dropna()
    close, high, low, volume = df["c"], df["h"], df["l"], df["v"]
    print(f"  {len(close)} bars: {close.index[0].date()} → {close.index[-1].date()}")

    scores = {
        "td": td_score_series(close, high, low),
        "cmf": cmf_score_series(close, high, low, volume),
        "st": st_score_series(high, low, close),
    }
    print(
        f"Walk-forward cycle scores (lookback={LOOKBACK_BARS}, refresh={CYCLE_REFRESH}, "
        f"use_dfe={use_dfe}) …"
    )
    scores["cycle"] = build_cycle_scores(
        close, WARMUP_BARS, LOOKBACK_BARS, CYCLE_REFRESH, use_dfe=use_dfe
    )

    comp = pd.DataFrame(
        {k: scores[k] for k in ("td", "cycle", "cmf", "st")},
        index=close.index,
    )
    comp["close"] = close
    comp.to_csv(out_dir / "component_scores.csv")

    if cycle_only:
        grid = [WeightSet(0.0, 1.0, 0.0, 0.0)]
        thresholds = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35]
        print(f"Cycle-only: 1 weight × {len(thresholds)} thresholds …")
    else:
        thresholds = [0.0, 0.15, 0.25, 0.35]
        grid = weight_grid(step=0.2)
        print(f"Grid search: {len(grid)} weight sets × {len(thresholds)} thresholds …")

    rows = []
    best_sharpe = None
    best_dd = None
    best_user = None
    best_sharpe_res = best_dd_res = best_user_res = None

    for w in grid:
        for thr in thresholds:
            res = simulate(close, scores, w, thr)
            s, b = res["strategy"], res["buyhold"]
            if not s or not b:
                continue
            row = {
                "w_td": w.td,
                "w_cycle": w.cycle,
                "w_cmf": w.cmf,
                "w_st": w.st,
                "threshold": thr,
                "strat_total": s["total_return"],
                "strat_cagr": s["cagr"],
                "strat_sharpe": s["sharpe"],
                "strat_max_dd": s["max_dd"],
                "strat_exposure": s["exposure"],
                "strat_trades": s["n_trades"],
                "bh_total": b["total_return"],
                "bh_cagr": b["cagr"],
                "bh_sharpe": b["sharpe"],
                "bh_max_dd": b["max_dd"],
                "beat_bh_total": s["total_return"] > b["total_return"],
                "beat_bh_sharpe": s["sharpe"] > b["sharpe"],
            }
            rows.append(row)
            if best_sharpe is None or row["strat_sharpe"] > best_sharpe["strat_sharpe"]:
                best_sharpe = row
                best_sharpe_res = res
            if best_dd is None or row["strat_max_dd"] > best_dd["strat_max_dd"]:
                best_dd = row
                best_dd_res = res
            if (
                not cycle_only
                and abs(w.td - 0.35) < 1e-6
                and abs(w.cycle - 0.45) < 1e-6
                and abs(thr - 0.15) < 1e-6
            ):
                best_user = row
                best_user_res = res

    results = pd.DataFrame(rows).sort_values("strat_sharpe", ascending=False)
    results.to_csv(out_dir / "grid_results.csv", index=False)

    refine_df = results
    if not cycle_only:
        top = results.head(5)
        refine_ws = []
        for _, r in top.iterrows():
            for d_td in (-0.1, 0.0, 0.1):
                for d_cy in (-0.1, 0.0, 0.1):
                    for d_cm in (-0.1, 0.0, 0.1):
                        td = np.clip(r["w_td"] + d_td, 0, 1)
                        cy = np.clip(r["w_cycle"] + d_cy, 0, 1)
                        cm = np.clip(r["w_cmf"] + d_cm, 0, 1)
                        st = 1.0 - td - cy - cm
                        if st < -1e-9 or st > 1 + 1e-9:
                            continue
                        refine_ws.append(
                            WeightSet(float(td), float(cy), float(cm), float(max(0, st)))
                        )
        refine_ws.append(WeightSet(0.35, 0.45, 0.10, 0.10))

        refine_rows = []
        for w in refine_ws:
            for thr in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
                res = simulate(close, scores, w, thr)
                s, b = res["strategy"], res["buyhold"]
                if not s:
                    continue
                row = {
                    "w_td": round(w.normalized().td, 4),
                    "w_cycle": round(w.normalized().cycle, 4),
                    "w_cmf": round(w.normalized().cmf, 4),
                    "w_st": round(w.normalized().st, 4),
                    "threshold": thr,
                    "strat_total": s["total_return"],
                    "strat_cagr": s["cagr"],
                    "strat_sharpe": s["sharpe"],
                    "strat_max_dd": s["max_dd"],
                    "strat_exposure": s["exposure"],
                    "strat_trades": s["n_trades"],
                    "bh_total": b["total_return"],
                    "bh_cagr": b["cagr"],
                    "bh_sharpe": b["sharpe"],
                    "bh_max_dd": b["max_dd"],
                    "beat_bh_total": s["total_return"] > b["total_return"],
                    "beat_bh_sharpe": s["sharpe"] > b["sharpe"],
                }
                refine_rows.append(row)
                if row["strat_sharpe"] > best_sharpe["strat_sharpe"]:
                    best_sharpe = row
                    best_sharpe_res = res
                if row["strat_max_dd"] > best_dd["strat_max_dd"]:
                    best_dd = row
                    best_dd_res = res
        refine_df = pd.DataFrame(refine_rows).sort_values("strat_sharpe", ascending=False)
        refine_df.to_csv(out_dir / "grid_refine.csv", index=False)

    if best_user is None:
        # For cycle-only, "user" slot stores the cycle-only best as N/A fixed blend on cycle scores
        res = simulate(close, scores, WeightSet(0.35, 0.45, 0.10, 0.10), 0.15)
        s, b = res["strategy"], res["buyhold"]
        best_user = {
            "w_td": 0.35,
            "w_cycle": 0.45,
            "w_cmf": 0.10,
            "w_st": 0.10,
            "threshold": 0.15,
            "strat_total": s["total_return"],
            "strat_cagr": s["cagr"],
            "strat_sharpe": s["sharpe"],
            "strat_max_dd": s["max_dd"],
            "strat_exposure": s["exposure"],
            "strat_trades": s["n_trades"],
            "bh_total": b["total_return"],
            "bh_cagr": b["cagr"],
            "bh_sharpe": b["sharpe"],
            "bh_max_dd": b["max_dd"],
            "beat_bh_total": s["total_return"] > b["total_return"],
            "beat_bh_sharpe": s["sharpe"] > b["sharpe"],
        }
        best_user_res = res

    def equity_curve(res) -> list[dict]:
        i0 = res["start_i"]
        dates = res["dates"][i0:]
        eq = res["equity"][i0:]
        bh = res["bh_equity"][i0:]
        ser = pd.DataFrame(
            {"date": dates, "strategy": eq / eq[0], "buyhold": bh / bh[0]}
        ).set_index("date")
        monthly = ser.resample("ME").last().dropna()
        return [
            {
                "date": d.strftime("%Y-%m-%d"),
                "strategy": round(float(r.strategy), 4),
                "buyhold": round(float(r.buyhold), 4),
            }
            for d, r in monthly.iterrows()
        ]

    all_cfgs = pd.concat([results, refine_df], ignore_index=True) if not cycle_only else results

    summary = {
        "symbol": symbol.upper(),
        "period_source": period_src,
        "mode": mode,
        "label": label,
        "start": str(close.index[WARMUP_BARS].date()),
        "end": str(close.index[-1].date()),
        "bars": int(len(close) - WARMUP_BARS),
        "cost_bps_per_side": COST_BPS,
        "lookback": LOOKBACK_BARS,
        "cycle_refresh": CYCLE_REFRESH,
        "buyhold": {
            "total_return": best_sharpe_res["buyhold"]["total_return"],
            "cagr": best_sharpe_res["buyhold"]["cagr"],
            "sharpe": best_sharpe_res["buyhold"]["sharpe"],
            "max_dd": best_sharpe_res["buyhold"]["max_dd"],
        },
        "user_blend_35_45_10_10": best_user,
        "best_sharpe": best_sharpe,
        "best_max_dd": best_dd,
        "n_grid": len(results),
        "n_beat_bh_total": int(results["beat_bh_total"].sum()),
        "n_beat_bh_sharpe": int(results["beat_bh_sharpe"].sum()),
        "n_refine_beat_bh_total": int(all_cfgs["beat_bh_total"].sum()),
        "top10_sharpe": results.head(10).to_dict(orient="records"),
        "top10_min_dd": results.sort_values("strat_max_dd", ascending=False)
        .head(10)
        .to_dict(orient="records"),
        "equity_best_sharpe": equity_curve(best_sharpe_res),
        "equity_user": equity_curve(best_user_res),
        "equity_best_dd": equity_curve(best_dd_res),
    }

    out_json = out_dir / "summary.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=float)
    print(f"Wrote {out_json}")
    print(
        f"  BH tot {summary['buyhold']['total_return']*100:.1f}% Sh {summary['buyhold']['sharpe']:.2f} | "
        f"Best tot {best_sharpe['strat_total']*100:.1f}% Sh {best_sharpe['strat_sharpe']:.2f} "
        f"DD {best_sharpe['strat_max_dd']*100:.1f}% "
        f"(beat tot={best_sharpe['beat_bh_total']}, beat sh={best_sharpe['beat_bh_sharpe']})"
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description="Multi-factor strategy vs buy-and-hold")
    parser.add_argument(
        "--symbol",
        nargs="+",
        default=["QQQ"],
        help="One or more Yahoo tickers",
    )
    parser.add_argument(
        "--use-dfe",
        action="store_true",
        help="Auto-detect periods with DFE each refresh (default: fixed DEFAULT_PERIODS)",
    )
    parser.add_argument(
        "--cycle-only",
        action="store_true",
        help="Ignore TD/CMF/ST; weight = 100%% cycle projection; sweep thresholds only",
    )
    parser.add_argument(
        "--out-root",
        default=None,
        help="Override output root (default tmp/backtest/<label>/)",
    )
    args = parser.parse_args()
    summaries = []
    for sym in args.symbol:
        out = None
        if args.out_root:
            out = Path(args.out_root) / sym.upper()
        summaries.append(
            run_backtest(
                sym.upper(),
                out_dir=out,
                use_dfe=args.use_dfe,
                cycle_only=args.cycle_only,
            )
        )
    if len(summaries) >= 1:
        compare = []
        for s in summaries:
            u, b, bs = s["user_blend_35_45_10_10"], s["buyhold"], s["best_sharpe"]
            compare.append(
                {
                    "symbol": s["symbol"],
                    "period_source": s["period_source"],
                    "mode": s["mode"],
                    "bh_total": b["total_return"],
                    "bh_cagr": b["cagr"],
                    "bh_sharpe": b["sharpe"],
                    "bh_max_dd": b["max_dd"],
                    "user_total": u["strat_total"],
                    "user_sharpe": u["strat_sharpe"],
                    "user_max_dd": u["strat_max_dd"],
                    "user_beat_bh_total": u["beat_bh_total"],
                    "best_sharpe": bs["strat_sharpe"],
                    "best_total": bs["strat_total"],
                    "best_max_dd": bs["strat_max_dd"],
                    "best_cagr": bs["strat_cagr"],
                    "best_exposure": bs["strat_exposure"],
                    "best_w_td": bs["w_td"],
                    "best_w_cycle": bs["w_cycle"],
                    "best_w_cmf": bs["w_cmf"],
                    "best_w_st": bs["w_st"],
                    "best_thr": bs["threshold"],
                    "best_beat_bh_total": bs["beat_bh_total"],
                    "best_beat_bh_sharpe": bs["beat_bh_sharpe"],
                    "n_beat_bh_total": s["n_beat_bh_total"],
                    "n_beat_bh_sharpe": s["n_beat_bh_sharpe"],
                }
            )
        label = summaries[0]["label"]
        out = (Path(args.out_root) if args.out_root else ROOT_OUT / label) / "compare_summary.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(compare, f, indent=2, default=float)
        print(f"\n===== Compare → {out} =====")
        for c in compare:
            print(
                f"{c['symbol']:5s}  BH_Sh {c['bh_sharpe']:.2f}  Best_Sh {c['best_sharpe']:.2f}  "
                f"BH_tot {c['bh_total']*100:7.1f}% Best_tot {c['best_total']*100:7.1f}%"
            )


if __name__ == "__main__":
    main()
