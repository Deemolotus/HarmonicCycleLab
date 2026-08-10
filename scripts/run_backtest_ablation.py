#!/usr/bin/env python3
"""
Run fixed/DFE × grid/cycle-only ablation for all study symbols; write master table.

对研究标的跑「固定/DFE × 网格/仅周期」消融，并写出总表。
"""

from __future__ import annotations

import json
from pathlib import Path

import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_strategy_backtest as bt

SYMBOLS = [
    "QQQ",
    "VOO",
    "GLD",
    "IWM",
    "XLC",
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "XLI",
    "XLY",
    "XLP",
    "XLU",
    "XLB",
    "XLRE",
]

NAMES = {
    "QQQ": "纳指ETF",
    "VOO": "标普ETF",
    "GLD": "黄金",
    "IWM": "小盘罗素2000",
    "XLC": "通信服务",
    "XLK": "科技",
    "XLF": "金融",
    "XLE": "能源",
    "XLV": "医疗保健",
    "XLI": "工业",
    "XLY": "可选消费",
    "XLP": "必选消费",
    "XLU": "公用事业",
    "XLB": "原材料",
    "XLRE": "房地产",
}

MODES = [
    ("fixed_grid", False, False),
    ("dfe_grid", True, False),
    ("fixed_cycle_only", False, True),
    ("dfe_cycle_only", True, True),
]


def row_from_summary(s: dict) -> dict:
    b, bs = s["buyhold"], s["best_sharpe"]
    return {
        "symbol": s["symbol"],
        "name": NAMES.get(s["symbol"], s["symbol"]),
        "period_source": s["period_source"],
        "mode": s["mode"],
        "label": s["label"],
        "start": s["start"],
        "end": s["end"],
        "bh_total": b["total_return"],
        "bh_cagr": b["cagr"],
        "bh_sharpe": b["sharpe"],
        "bh_max_dd": b["max_dd"],
        "best_total": bs["strat_total"],
        "best_cagr": bs["strat_cagr"],
        "best_sharpe": bs["strat_sharpe"],
        "best_max_dd": bs["strat_max_dd"],
        "best_exposure": bs["strat_exposure"],
        "best_trades": bs.get("strat_trades", bs.get("n_trades")),
        "w_td": bs["w_td"],
        "w_cycle": bs["w_cycle"],
        "w_cmf": bs["w_cmf"],
        "w_st": bs["w_st"],
        "thr": bs["threshold"],
        "beat_bh_total": bs["beat_bh_total"],
        "beat_bh_sharpe": bs["beat_bh_sharpe"],
        "n_beat_bh_total": s["n_beat_bh_total"],
        "n_beat_bh_sharpe": s["n_beat_bh_sharpe"],
    }


def main():
    all_rows = []
    for label, use_dfe, cycle_only in MODES:
        print(f"\n######## MODE {label} ########")
        mode_rows = []
        for sym in SYMBOLS:
            summary = bt.run_backtest(sym, use_dfe=use_dfe, cycle_only=cycle_only, tag=label)
            r = row_from_summary(summary)
            mode_rows.append(r)
            all_rows.append(r)
        out = bt.ROOT_OUT / label / "compare_summary.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(mode_rows, f, indent=2, default=float)
        print(f"Wrote {out}")

    master = bt.ROOT_OUT / "master_results.json"
    with open(master, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, indent=2, default=float)
    print(f"\nMaster → {master} ({len(all_rows)} rows)")


if __name__ == "__main__":
    main()
