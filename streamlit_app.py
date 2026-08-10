"""
HarmonicCycleLab — Streamlit web app for harmonic-cycle charts and indicators.

HarmonicCycleLab — 谐波周期图表与指标的 Streamlit Web 应用。
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from datetime import date

import pandas as pd
import streamlit as st

import cycle_engine as qe

PLOTLY_CONFIG = {"scrollZoom": True, "displaylogo": False}

APP_NAME = "HarmonicCycleLab"

# UI copy keyed by language. / 按语言切换的界面文案。
_UI = {
    "en": {
        "lang_label": "Language",
        "cycle": "Cycle",
        "symbol": "Ticker",
        "end_date": "End date (YYYY-MM-DD)",
        "start_date": "Start date (optional)",
        "start_help": "Blank → auto lookback (678–900)",
        "lookback": "Lookback bars (optional)",
        "future": "Forward projection (days)",
        "auto_dfe": "Auto-detect periods (DFE)",
        "periods": "Cycle periods (trading days)",
        "show_st": "Show SuperTrend",
        "show_td": "Show TD overlays",
        "show_td_setup": "Show TD9 Setup",
        "show_td_cd": "Show TD13/15 countdown",
        "show_td_nums": "Show per-bar counts",
        "show_sqz": "Show Squeeze pane",
        "run": "Run",
        "idle": "Set the sidebar, then click **Run**.",
        "spinner": "Running… auto lookback may take 30–90s",
        "fail": "Analysis failed — check inputs or retry.",
        "download": "Download HTML chart",
        "engine": "Engine log",
        "periods_cap": "Detected periods",
        "fetch": "Fetching {symbol}…",
        "auto_lb_fetch": "Auto lookback: downloading max window for DFE + sweep…",
        "downloaded": "  Downloaded {n} bars ({start} → {end})",
        "few_bars": "  Warning: only {n} bars; recommended minimum {min}.",
        "auto_lb": "Selecting lookback (period floor + stability sweep)…",
        "periods_log": "Periods: [{periods}] d  (source: {src})  lookback: {lb} bars",
        "fit": "Fit R²={r2:.4f}  ranked={ranked}",
    },
    "zh": {
        "lang_label": "语言",
        "cycle": "周期",
        "symbol": "代码",
        "end_date": "结束日 (YYYY-MM-DD)",
        "start_date": "起始日（可选）",
        "start_help": "留空 → 自动 lookback（678–900）",
        "lookback": "回看根数（可选）",
        "future": "向前投影（交易日）",
        "auto_dfe": "自动识别周期（DFE）",
        "periods": "周期长度（交易日）",
        "show_st": "显示 SuperTrend",
        "show_td": "显示 TD 叠加",
        "show_td_setup": "显示 TD9 Setup",
        "show_td_cd": "显示 TD13/15 Countdown",
        "show_td_nums": "显示逐根计数",
        "show_sqz": "显示 Squeeze 副图",
        "run": "运行",
        "idle": "在左侧设好参数，再点 **运行**。",
        "spinner": "分析中…自动 lookback 大约 30–90 秒",
        "fail": "分析失败，请检查参数或稍后重试。",
        "download": "下载 HTML 图表",
        "engine": "引擎日志",
        "periods_cap": "检测周期",
        "fetch": "正在获取 {symbol}…",
        "auto_lb_fetch": "自动 lookback：拉取最大窗口供 DFE 与扫描…",
        "downloaded": "  已下载 {n} 根（{start} → {end}）",
        "few_bars": "  警告：仅有 {n} 根，建议至少 {min}。",
        "auto_lb": "正在选择 lookback（周期下限 + 稳定性扫描）…",
        "periods_log": "周期: [{periods}] 日  (来源: {src})  lookback: {lb} 根",
        "fit": "拟合 R²={r2:.4f}  排序={ranked}",
    },
}


@dataclass
class AnalysisParams:
    """Sidebar analysis parameters. / 侧边栏分析参数。"""

    lang: str
    symbol: str
    end_date: str
    start_date: str
    lookback: str
    future_days: int
    auto_dfe: bool
    periods: list[float] | None
    show_st: bool
    st_len: int
    st_mult: float
    show_td: bool
    show_td_setup: bool
    show_td_cd: bool
    show_td_nums: bool
    cd_tgt: int
    cd_ext: int
    show_sqz: bool
    sqz_bb_len: int
    sqz_bb_mult: float
    sqz_kc_len: int
    sqz_kc_mult: float


def run_analysis(params: AnalysisParams) -> dict:
    """
    Run the full analysis pipeline; returns fig, log text, and detected periods.

    跑完整分析流水线；返回图表、日志与检测到的周期。
    """
    ui = _UI[params.lang]
    log: list[str] = []
    symbol = params.symbol.strip() or qe.DEFAULT_SYMBOL
    end_date = params.end_date.strip() or date.today().isoformat()
    start_date = params.start_date.strip()
    lb_str = params.lookback.strip()
    future_days = params.future_days

    log.append(ui["fetch"].format(symbol=symbol))

    explicit_lookback = None
    auto_lookback = False
    if start_date:
        pass
    elif lb_str:
        explicit_lookback = int(lb_str)
        start_date = (pd.Timestamp(end_date) - pd.offsets.BDay(explicit_lookback)).date().isoformat()
    else:
        auto_lookback = True
        start_date = (pd.Timestamp(end_date) - pd.offsets.BDay(qe.MAX_LOOKBACK_BARS)).date().isoformat()
        log.append(ui["auto_lb_fetch"])

    close, high, low, volume = qe.download_ohlcv(symbol, start_date, end_date)
    log.append(ui["downloaded"].format(n=len(close), start=start_date, end=end_date))
    if len(close) < qe.MIN_LOOKBACK_BARS:
        log.append(ui["few_bars"].format(n=len(close), min=qe.MIN_LOOKBACK_BARS))

    if auto_lookback:
        log.append(ui["auto_lb"])

    cfg = qe.resolve_cycle_config(
        close, high, low, volume,
        periods_manual=params.periods,
        auto_dfe=params.auto_dfe,
        future_days=future_days,
        explicit_lookback=explicit_lookback,
        auto_lookback=auto_lookback,
        log_cb=lambda m: log.append(m),
        lang=params.lang,
    )
    close, high, low, volume = cfg["close"], cfg["high"], cfg["low"], cfg["volume"]
    periods = cfg["periods"]
    for msg in cfg["messages"]:
        log.append(msg)

    period_str = ", ".join(f"{p:.1f}" for p in periods)
    log.append(ui["periods_log"].format(
        periods=period_str, src=cfg["periods_source"], lb=cfg["lookback_bars"]
    ))

    m = qe.metrics_for_window(close, periods, future_days, lang=params.lang)
    overlay, cs = m["overlay"], m["cycle_stats"]
    log.append(ui["fit"].format(r2=m["combined_r2"], ranked=[int(p) for p in m["ranked_periods"]]))
    log.append(m["timing_report"])

    trend, st_line = qe.calculate_supertrend(high, low, close, params.st_len, params.st_mult)
    _, _, sigs = qe.td_sequential(close, high, low, params.cd_tgt, params.cd_ext)
    sqz_val, _, _, _, _, _ = qe.squeeze_momentum(
        close, high, low,
        params.sqz_bb_len, params.sqz_bb_mult, params.sqz_kc_len, params.sqz_kc_mult,
    )
    # Blend CMF-style flow with signed volume for confirmation.
    # 用 CMF 风格资金流与涨跌量混合作为确认。
    cmf_val = qe.flow_pressure(close, high, low, volume, n=10, signed_weight=0.55)

    trade_advice = qe.analyze_trade_state(
        close, low, high, trend, st_line, sigs, sqz_val, cmf_val,
        cycle_metrics=m, lang=params.lang,
    )
    log.append(trade_advice)

    fig = qe.build_plotly_chart(
        close, overlay, cs, symbol, periods, high, low,
        params.show_td, params.show_td_setup, params.show_td_cd, params.show_td_nums,
        params.cd_tgt, params.cd_ext,
        params.show_sqz, params.sqz_bb_len, params.sqz_bb_mult, params.sqz_kc_len, params.sqz_kc_mult,
        params.show_st, params.st_len, params.st_mult, cmf_val,
        projection_extrema=m.get("projection_extrema"),
    )

    return {
        "fig": fig,
        "log": "\n".join(log),
        "symbol": symbol,
        "periods": periods,
        "lang": params.lang,
    }


def build_sidebar() -> AnalysisParams | None:
    """
    Collect sidebar inputs; return params when Run is clicked.

    收集侧边栏输入；点击运行后返回参数。
    """
    st.sidebar.title(APP_NAME)

    lang_choice = st.sidebar.radio(
        "Language / 语言",
        options=["en", "zh"],
        format_func=lambda x: "English" if x == "en" else "中文",
        horizontal=True,
        key="ui_lang",
    )
    ui = _UI[lang_choice]

    st.sidebar.subheader(ui["cycle"])
    symbol = st.sidebar.text_input(ui["symbol"], value=qe.DEFAULT_SYMBOL)
    end_date = st.sidebar.text_input(ui["end_date"], value=date.today().isoformat())
    start_date = st.sidebar.text_input(ui["start_date"], value="", help=ui["start_help"])
    lookback = st.sidebar.text_input(ui["lookback"], value="")
    future_days = st.sidebar.number_input(
        ui["future"],
        min_value=1,
        max_value=365,
        value=qe.DEFAULT_FUTURE_DAYS,
    )

    auto_dfe = st.sidebar.checkbox(ui["auto_dfe"], value=True)
    st.sidebar.markdown(f"**{ui['periods']}**")
    c1, c2, c3 = st.sidebar.columns(3)
    p1 = c1.text_input("P1", value=str(qe.DEFAULT_PERIODS[0]), disabled=auto_dfe, label_visibility="collapsed")
    p2 = c2.text_input("P2", value=str(qe.DEFAULT_PERIODS[1]), disabled=auto_dfe, label_visibility="collapsed")
    p3 = c3.text_input("P3", value=str(qe.DEFAULT_PERIODS[2]), disabled=auto_dfe, label_visibility="collapsed")

    periods_manual = None
    if not auto_dfe:
        raw = [p.strip() for p in (p1, p2, p3) if p.strip()]
        periods_manual = [float(x) for x in raw] if raw else None

    st.sidebar.divider()
    st.sidebar.subheader("SuperTrend")
    show_st = st.sidebar.checkbox(ui["show_st"], value=True)
    st_col1, st_col2 = st.sidebar.columns(2)
    st_len = st_col1.number_input("ATR Period", min_value=1, value=10)
    st_mult = st_col2.number_input("Multiplier", min_value=0.1, value=3.0, step=0.1)

    st.sidebar.divider()
    st.sidebar.subheader("TD Sequential")
    show_td = st.sidebar.checkbox(ui["show_td"], value=True)
    show_td_setup = st.sidebar.checkbox(ui["show_td_setup"], value=True)
    show_td_cd = st.sidebar.checkbox(ui["show_td_cd"], value=True)
    show_td_nums = st.sidebar.checkbox(ui["show_td_nums"], value=False)
    cd_col1, cd_col2 = st.sidebar.columns(2)
    cd_tgt = cd_col1.number_input("Countdown", min_value=1, value=13)
    cd_ext = cd_col2.number_input("Extended", min_value=1, value=15)

    st.sidebar.divider()
    st.sidebar.subheader("Squeeze Momentum")
    show_sqz = st.sidebar.checkbox(ui["show_sqz"], value=True)
    sqz_col1, sqz_col2 = st.sidebar.columns(2)
    sqz_bb_len = sqz_col1.number_input("BB Length", min_value=1, value=20)
    sqz_bb_mult = sqz_col2.number_input("BB Mult", min_value=0.1, value=2.0, step=0.1)
    sqz_col3, sqz_col4 = st.sidebar.columns(2)
    sqz_kc_len = sqz_col3.number_input("KC Length", min_value=1, value=20)
    sqz_kc_mult = sqz_col4.number_input("KC Mult", min_value=0.1, value=1.5, step=0.1)

    run_clicked = st.sidebar.button(ui["run"], type="primary", use_container_width=True)

    params = AnalysisParams(
        lang=lang_choice,
        symbol=symbol,
        end_date=end_date,
        start_date=start_date,
        lookback=lookback,
        future_days=int(future_days),
        auto_dfe=auto_dfe,
        periods=periods_manual,
        show_st=show_st,
        st_len=int(st_len),
        st_mult=float(st_mult),
        show_td=show_td,
        show_td_setup=show_td_setup,
        show_td_cd=show_td_cd,
        show_td_nums=show_td_nums,
        cd_tgt=int(cd_tgt),
        cd_ext=int(cd_ext),
        show_sqz=show_sqz,
        sqz_bb_len=int(sqz_bb_len),
        sqz_bb_mult=float(sqz_bb_mult),
        sqz_kc_len=int(sqz_kc_len),
        sqz_kc_mult=float(sqz_kc_mult),
    )
    return params if run_clicked else None


def main() -> None:
    st.set_page_config(
        page_title=APP_NAME,
        layout="wide",
    )
    st.title(APP_NAME)

    params = build_sidebar()
    lang = st.session_state.get("ui_lang", "en")
    ui = _UI[lang]

    if params is None:
        st.info(ui["idle"])
        if "last_result" in st.session_state:
            result = st.session_state["last_result"]
            _render_result(result)
        return

    try:
        with st.spinner(ui["spinner"]):
            result = run_analysis(params)
        st.session_state["last_result"] = result
        _render_result(result)
    except qe.DataFetchError as exc:
        st.error(str(exc))
    except Exception:
        st.error(ui["fail"])
        st.code(traceback.format_exc())


def _render_result(result: dict) -> None:
    """Render chart, download, and engine log. / 渲染图表、下载与引擎日志。"""
    lang = result.get("lang") or st.session_state.get("ui_lang", "en")
    ui = _UI[lang]
    st.plotly_chart(result["fig"], use_container_width=True, config=PLOTLY_CONFIG)

    html_bytes = result["fig"].to_html(
        include_plotlyjs="cdn",
        config=PLOTLY_CONFIG,
    ).encode("utf-8")
    st.download_button(
        label=ui["download"],
        data=html_bytes,
        file_name=f"{result['symbol']}_HarmonicCycleLab.html",
        mime="text/html",
    )

    with st.expander(ui["engine"], expanded=True):
        st.code(result["log"], language=None)

    period_str = ", ".join(f"{p:.1f}" for p in result["periods"])
    st.caption(f"{ui['periods_cap']}: [{period_str}] d")


if __name__ == "__main__":
    main()
