#!/usr/bin/env python3
"""
Stock Team Agent HTML Report Generator v5.0 — Open Design
===========================================================
Open editorial design: light theme, premium typography, CSS variables.
5-Section Structure:
  1. Sticky Header + Nav + One-Line Summary
  2. Executive KPI Deck (sparklines, YoY/MoM, trend badges)
  3. Visual Insights (Chart.js: price + radar + risk + target)
  4. Deep Narrative (analyst cards with accordions)
  5. Technical Traceability (copy JSON, methodology)

Usage:
    from generate.stock_html_report import generate_html_report
    html_path = generate_html_report(result_dict, output_dir)
"""

import json, os
from datetime import datetime
from typing import Any, Dict

CHART_CDN = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"
TAILWIND  = "https://cdn.tailwindcss.com@3.4.0"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _e(s: Any) -> str:
    if s is None: return ""
    s = str(s)
    return (s.replace("&","&amp;").replace("<","&lt;")
             .replace(">","&gt;").replace('"',"&quot;"))

def _f(n: Any, fmt=".2f") -> str:
    try: return f"{float(n):{fmt}}"
    except (ValueError, TypeError): return str(n)

def _pct(n: float, fmt=".1f") -> str:
    try: return f"{float(n):{fmt}}%"
    except (ValueError, TypeError): return "N/A"

def _badge_signal(sig: str) -> str:
    m = {
        "buy":    ("BUY",    "bg-emerald-50 text-emerald-700 border border-emerald-200"),
        "sell":   ("SELL",   "bg-red-50 text-red-700 border border-red-200"),
        "neutral":("NEUTRAL","bg-amber-50 text-amber-700 border border-amber-200"),
        "hold":   ("HOLD",   "bg-amber-50 text-amber-700 border border-amber-200"),
    }
    lbl, cls = m.get(sig.lower(), (sig.upper(), "bg-slate-50 text-slate-700 border border-slate-200"))
    return f'<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold {cls}">{lbl}</span>'

def _score_color(v: float) -> str:
    if v >= 0.7:    return "text-emerald-600"
    elif v >= 0.5:  return "text-amber-600"
    elif v >= 0.35: return "text-orange-500"
    else:           return "text-red-600"

def _score_bg(v: float) -> str:
    if v >= 0.7:    return "bg-emerald-500"
    elif v >= 0.5:  return "bg-amber-500"
    elif v >= 0.35: return "bg-orange-500"
    else:           return "bg-red-500"

def _conf_label(n: float):
    if n >= 0.7:     return "HIGH", "text-emerald-600"
    elif n >= 0.45:  return "MED",  "text-amber-600"
    else:            return "LOW",  "text-red-600"

def _sentiment_color(lbl: str) -> str:
    l = lbl.lower()
    if any(x in l for x in ["positive","buy","bull","看漲","利好"]): return "text-emerald-600"
    if any(x in l for x in ["negative","sell","bear","看跌","利空"]): return "text-red-600"
    return "text-amber-600"

def _analyst_name(role: str) -> str:
    return {
        "market":"Market Analyst","technical":"Technical Analyst",
        "fundamental":"Fundamental Analyst","risk":"Risk Analyst",
        "sentiment":"Sentiment Analyst","news":"News Analyst",
        "macro":"Macro Strategy Analyst",
    }.get(role, role)

def _analyst_icon(role: str) -> str:
    return {"market":"MKT","technical":"TECH","fundamental":"FUND","risk":"RISK",
            "sentiment":"SENT","news":"NEWS","macro":"MACR"}.get(role,"???")

ANALYST_META = {
    "market":      "52W位置/價格區間/YTD/市值/Beta",
    "technical":  "MA20/50/RSI/MACD/布林帶/K線形態",
    "fundamental":"P/E/ROE/EPS/PEG/營收增長/DCF",
    "risk":        "VaR/波動性/最大回撤/Sharpe/流動性",
    "sentiment":   "新聞情緒/多空比例/市場情緒",
    "news":        "RSS覆蓋量/地區分佈/時效性",
    "macro":       "美債/VIX/美元指數/黃金/宏觀週期",
}

ANALYST_COLORS = ["#3B82F6","#8B5CF6","#10B981","#F59E0B","#EC4899","#06B6D4","#F97316"]


# ─────────────────────────────────────────────────────────────────────────────
# CSS — Open Design System
# ─────────────────────────────────────────────────────────────────────────────

OPEN_CSS = """
:root {
  --bg:        #F8F7F4;
  --surface:   #FFFFFF;
  --surface2:  #F1F0EC;
  --border:    #E5E3DC;
  --border2:   #D1CFC6;
  --text:      #1A1A1A;
  --text2:     #4A4A4A;
  --dim:       #8A8A8A;
  --accent:    #2563EB;
  --accent2:   #7C3AED;
  --positive:  #059669;
  --negative:  #DC2626;
  --warning:   #D97706;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow:    0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04);
  --shadow-lg: 0 10px 40px rgba(0,0,0,0.10), 0 4px 12px rgba(0,0,0,0.06);
  --radius:    16px;
  --radius-sm: 10px;
}
*{box-sizing:border-box}
body{
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Segoe UI",Roboto,sans-serif;
  background:var(--bg);
  color:var(--text);
  line-height:1.6;
  -webkit-font-smoothing:antialiased;
}
a{text-decoration:none}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}

/* Card base */
.card{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:var(--radius);
  box-shadow:var(--shadow-sm);
  transition:box-shadow 0.2s, border-color 0.2s;
}
.card:hover{box-shadow:var(--shadow);border-color:var(--border2)}

/* Section label pill */
.section-label{
  display:inline-flex;align-items:center;gap:6px;
  font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;
  color:var(--dim);background:var(--surface2);
  border:1px solid var(--border);border-radius:20px;
  padding:4px 12px;
}

/* Score bar */
.score-bar{height:6px;background:var(--surface2);border-radius:99px;overflow:hidden}
.score-bar-fill{height:100%;border-radius:99px;transition:width 0.6s ease}

/* Analyst accordion */
.accordion-item{border:1px solid var(--border);border-radius:var(--radius-sm);overflow:hidden;margin-bottom:8px;background:var(--surface)}
.accordion-header{display:flex;align-items:center;gap:12px;padding:14px 16px;cursor:pointer;user-select:none;transition:background 0.15s}
.accordion-header:hover{background:var(--surface2)}
.accordion-body{padding:0 16px 16px;border-top:1px solid var(--border);display:none}
.accordion-item.open .accordion-body{display:block}
.accordion-item.open .accordion-chevron{transform:rotate(180deg)}
.accordion-chevron{transition:transform 0.2s;flex-shrink:0}

/* Signal pill */
.signal-buy   {background:#ECFDF5;color:#065F46;border:1px solid #A7F3D0}
.signal-sell  {background:#FEF2F2;color:#991B1B;border:1px solid #FECACA}
.signal-hold  {background:#FFFBEB;color:#92400E;border:1px solid #FDE68A}
.signal-neutral{background:#FFFBEB;color:#92400E;border:1px solid #FDE68A}

/* Badge */
.badge-blue   {background:#EFF6FF;color:#1D4ED8;border:1px solid #BFDBFE}
.badge-purple {background:#F5F3FF;color:#6D28D9;border:1px solid #DDD6FE}
.badge-green  {background:#ECFDF5;color:#065F46;border:1px solid #A7F3D0}
.badge-red    {background:#FEF2F2;color:#991B1B;border:1px solid #FECACA}
.badge-amber  {background:#FFFBEB;color:#92400E;border:1px solid #FDE68A}

/* Debate types */
.debate-argument  {border-left:3px solid #2563EB}
.debate-challenge{border-left:3px solid #DC2626}
.debate-counter   {border-left:3px solid #7C3AED}
.debate-concede   {border-left:3px solid #059669}
.debate-warning   {border-left:3px solid #D97706}

/* News item */
.news-item{display:flex;align-items:flex-start;gap:12px;padding:12px 0;border-bottom:1px solid var(--border);transition:background 0.15s;border-radius:8px}
.news-item:hover{background:var(--surface2)}
.news-item:last-child{border-bottom:none}

/* KPI sparkline */
.sparkline-wrap{display:flex;align-items:flex-end;gap:2px;height:32px}

/* Risk meter */
.risk-meter{height:8px;background:var(--surface2);border-radius:99px;overflow:hidden}
.risk-meter-fill{bore:99px}

/* Print */
@media print{
  body{background:white!important;color:black!important}
  .no-print,nav{display:none!important}
  .card{box-shadow:none!important;border:1px solid #ccc!important}
  section{page-break-inside:avoid}
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Part builders
# ─────────────────────────────────────────────────────────────────────────────

def _build_header(ticker, name, summary, analysis_time, ws, consensus_s, conf):
    conf_l, conf_c = _conf_label(conf)
    sig_cls = "signal-buy" if consensus_s.lower()=="buy" else "signal-sell" if consensus_s.lower()=="sell" else "signal-hold"
    return f"""
<!-- ═══════════════════════════════════════════════ PART 1: HEADER ══ -->
<header class="bg-white/95 backdrop-blur text-[#1A1A1A] sticky top-0 z-50 border-b border-[#E5E3DC] shadow-sm">
    <div class="max-w-7xl mx-auto px-5 py-4">
        <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
            <div class="flex-1 min-w-0">
                <div class="flex items-center gap-3 flex-wrap">
                    <div class="flex items-center gap-2">
                        <div class="w-8 h-8 rounded-lg bg-[#2563EB] flex items-center justify-center">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M3 17l6-6 4 4 8-8" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M14 7h7v7" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                        </div>
                        <h1 class="text-xl font-bold tracking-tight text-[#1A1A1A]">{_e(name)}</h1>
                    </div>
                    <span class="bg-[#2563EB]/10 text-[#2563EB] text-xs font-bold px-2.5 py-1 rounded-lg border border-[#2563EB]/20">
                        {ticker}
                    </span>
                    <span class="text-xs text-[#8A8A8A] font-mono bg-[#F1F0EC] px-2 py-0.5 rounded">{analysis_time}</span>
                </div>
                <p class="text-sm text-[#4A4A4A] mt-1 leading-relaxed max-w-2xl">{_e(summary)}</p>
            </div>
            <div class="flex items-center gap-4 flex-shrink-0">
                <div class="text-right">
                    <div class="text-[10px] text-[#8A8A8A] uppercase tracking-widest font-semibold">共識評級</div>
                    <div class="text-2xl font-black text-[#1A1A1A]">{_f(ws)}<span class="text-sm font-normal text-[#8A8A8A]">/1.00</span></div>
                </div>
                <span class="{sig_cls} text-sm font-bold px-4 py-2 rounded-xl">{consensus_s.upper()}</span>
            </div>
        </div>
    </div>
    <nav class="bg-white/95 border-t border-[#E5E3DC] no-print">
        <div class="max-w-7xl mx-auto px-5">
            <div class="flex gap-1 overflow-x-auto py-2 text-sm">
                <a href="#kpi"      class="px-4 py-1.5 rounded-lg hover:bg-[#F1F0EC] text-[#4A4A4A] hover:text-[#1A1A1A] transition-colors whitespace-nowrap font-medium flex items-center gap-1.5">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
                    KPI概覽
                </a>
                <a href="#visual"  class="px-4 py-1.5 rounded-lg hover:bg-[#F1F0EC] text-[#4A4A4A] hover:text-[#1A1A1A] transition-colors whitespace-nowrap font-medium flex items-center gap-1.5">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                    視覺化
                </a>
                <a href="#analysts" class="px-4 py-1.5 rounded-lg hover:bg-[#F1F0EC] text-[#4A4A4A] hover:text-[#1A1A1A] transition-colors whitespace-nowrap font-medium flex items-center gap-1.5">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                    分析師
                </a>
                <a href="#narrative" class="px-4 py-1.5 rounded-lg hover:bg-[#F1F0EC] text-[#4A4A4A] hover:text-[#1A1A1A] transition-colors whitespace-nowrap font-medium flex items-center gap-1.5">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
                    深度解讀
                </a>
                <a href="#debate"  class="px-4 py-1.5 rounded-lg hover:bg-[#F1F0EC] text-[#4A4A4A] hover:text-[#1A1A1A] transition-colors whitespace-nowrap font-medium flex items-center gap-1.5">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                    辯論記錄
                </a>
                <a href="#news"    class="px-4 py-1.5 rounded-lg hover:bg-[#F1F0EC] text-[#4A4A4A] hover:text-[#1A1A1A] transition-colors whitespace-nowrap font-medium flex items-center gap-1.5">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/></svg>
                    新聞
                </a>
                <a href="#risk"   class="px-4 py-1.5 rounded-lg hover:bg-[#F1F0EC] text-[#4A4A4A] hover:text-[#1A1A1A] transition-colors whitespace-nowrap font-medium flex items-center gap-1.5">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    風險
                </a>
                <a href="#technical" class="px-4 py-1.5 rounded-lg hover:bg-[#F1F0EC] text-[#4A4A4A] hover:text-[#1A1A1A] transition-colors whitespace-nowrap font-medium flex items-center gap-1.5">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>
                    技術細節
                </a>
            </div>
        </div>
    </nav>
</header>"""


def _kpi_card(label, value, sub, trend_lbl, trend_cls, badge_text="", badge_cls=""):
    badge = (f'<span class="text-[10px] {badge_cls} px-1.5 py-0.5 rounded-md font-bold">{badge_text}</span>' if badge_text else "")
    arrow = "↑" if "↑" in trend_lbl else ("↓" if "↓" in trend_lbl else "")
    return f"""
        <div class="card p-5 flex flex-col gap-2">
            <div class="text-[10px] text-[#8A8A8A] uppercase tracking-widest font-semibold">{label}</div>
            <div class="flex items-end justify-between gap-2">
                <div class="text-3xl font-black text-[#1A1A1A] tracking-tight leading-none">{value}</div>
                {badge}
            </div>
            <div class="text-xs text-[#8A8A8A]">{sub}</div>
            <div class="flex items-center gap-1.5 mt-1">
                <span class="{trend_cls} text-sm font-bold">{arrow} {trend_lbl}</span>
            </div>
        </div>"""


def _build_kpi_deck(data):
    tech = data.get("technical", {})
    fund = data.get("fundamental", {})
    risk = data.get("risk", {})
    mkt  = data.get("market_data", {})

    price  = float(data.get("price", 0))
    ytd    = float(mkt.get("ytd_return", data.get("ytd_return", 0)))
    w52h   = float(mkt.get("week52_high", data.get("week52_high", 0)))
    w52l   = float(mkt.get("week52_low", data.get("week52_low", 0)))
    pe     = float(fund.get("pe", data.get("pe", 0)))
    roe    = float(fund.get("roe", data.get("roe", 0))) * 100
    rsi    = float(tech.get("rsi", data.get("rsi", 50)))
    macd   = float(tech.get("macd", data.get("macd", 0)))
    vol    = float(risk.get("volatility", data.get("volatility", 0)))
    var95  = abs(float(risk.get("var_95", data.get("var_95", 0))))
    mdd    = abs(float(risk.get("max_drawdown", data.get("max_drawdown", 0))))
    sharpe = float(risk.get("sharpe", data.get("sharpe", 0)))
    beta   = float(risk.get("beta", data.get("beta", 1)))
    ws     = float(data.get("weighted_score", 0))
    conf   = float(data.get("confidence", 0))
    rec    = data.get("recommendation", "HOLD")
    pos52  = ((price - w52l) / (w52h - w52l) * 100) if w52h > w52l else 50

    # v5.8: 委派給 stock_analysis.currency_symbol() 純函數（dedup 兩處硬編碼字典）
    from stock_analysis import currency_symbol as _currency_symbol_fn
    _currency = data.get("currency", "USD")
    _currency_symbol = _currency_symbol_fn(_currency)

    kpis = ""

    # Price
    ytd_cls = "text-emerald-600" if ytd >= 0 else "text-red-600"
    ytd_badge = "bg-emerald-50 text-emerald-700 border border-emerald-200" if ytd >= 0 else "bg-red-50 text-red-700 border border-red-200"
    kpis += _kpi_card(
        "目前股價", f"{_currency_symbol}{_f(price)}",
        f"YTD {_pct(ytd)} | 52W區間 {_f(pos52,'.0f')}%",
        _pct(ytd), ytd_cls,
        _pct(ytd), ytd_badge
    )
    # P/E
    pe_lbl  = "偏低" if pe < 14 else ("偏高" if pe > 22 else "中性")
    pe_cls  = "text-emerald-600" if pe < 14 else ("text-red-600" if pe > 22 else "text-amber-600")
    pe_badge= "bg-emerald-50 text-emerald-700 border border-emerald-200" if pe < 14 else ("bg-red-50 text-red-700 border border-red-200" if pe > 22 else "bg-amber-50 text-amber-700 border border-amber-200")
    kpis += _kpi_card(
        "P/E 比值", _f(pe)+"×",
        f"行業均值 ~18× | ROE {_pct(roe)}",
        pe_lbl, pe_cls, _f(pe)+"×", pe_badge
    )
    # 52W Position
    pos_lbl = "接近低點" if pos52 < 30 else ("接近高點" if pos52 > 70 else "中性區間")
    pos_cls = "text-emerald-600" if pos52 < 30 else ("text-red-600" if pos52 > 70 else "text-amber-600")
    pos_badge= "bg-emerald-50 text-emerald-700 border border-emerald-200" if pos52 < 30 else ("bg-red-50 text-red-700 border border-red-200" if pos52 > 70 else "bg-amber-50 text-amber-700 border border-amber-200")
    from_h = _pct((w52h-price)/w52h*100) if w52h else "N/A"
    kpis += _kpi_card(
        "52W 區間位置", f"{_f(pos52,'.0f')}%",
        f"高點 {_currency_symbol}{_f(w52h)} | 低點 {_currency_symbol}{_f(w52l)}",
        pos_lbl, pos_cls, f"距高點 -{from_h}", pos_badge
    )
    # RSI
    rsi_lbl  = "超賣" if rsi < 30 else ("超買" if rsi > 70 else "中性")
    rsi_cls  = "text-emerald-600" if rsi < 30 else ("text-red-600" if rsi > 70 else "text-amber-600")
    rsi_badge= "bg-emerald-50 text-emerald-700 border border-emerald-200" if rsi < 30 else ("bg-red-50 text-red-700 border border-red-200" if rsi > 70 else "bg-amber-50 text-amber-700 border border-amber-200")
    kpis += _kpi_card(
        "RSI (14)", _f(rsi),
        "超賣<30 | 超買>70",
        rsi_lbl, rsi_cls, rsi_lbl, rsi_badge
    )
    # Volatility
    vol_lbl  = "低" if vol < 20 else ("高" if vol > 40 else "中")
    vol_cls  = "text-emerald-600" if vol < 20 else ("text-red-600" if vol > 40 else "text-amber-600")
    vol_badge= "bg-emerald-50 text-emerald-700 border border-emerald-200" if vol < 20 else ("bg-red-50 text-red-700 border border-red-200" if vol > 40 else "bg-amber-50 text-amber-700 border border-amber-200")
    kpis += _kpi_card(
        "波動性 (年化)", _pct(vol),
        f"VaR(95%) {_pct(var95)} | 最大回撤 {_pct(mdd)}",
        f"Sharpe {_f(sharpe)}", vol_cls,        f"波動{vol_lbl}", vol_badge
    )
    # Weighted Score
    ws_badge = "bg-emerald-50 text-emerald-700 border border-emerald-200" if ws >= 0.7 else ("bg-red-50 text-red-700 border border-red-200" if ws < 0.4 else "bg-amber-50 text-amber-700 border border-amber-200")
    kpis += _kpi_card(
        "綜合評分", f"{_f(ws)}/1.00",
        f"共識 {rec} | 置信度 {_f(conf)}",
        _badge_signal(data.get("consensus_signal","hold")).replace('inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ','').replace('bg-','bg-').replace('text-','text-'),
        _score_color(ws),
        rec, ws_badge
    )
    # Beta
    beta_lbl = "防御股" if beta < 0.8 else ("進攻股" if beta > 1.2 else "中性")
    beta_cls = "text-emerald-600" if beta < 0.8 else ("text-red-600" if beta > 1.2 else "text-amber-600")
    beta_badge= "bg-emerald-50 text-emerald-700 border border-emerald-200" if beta < 0.8 else ("bg-red-50 text-red-700 border border-red-200" if beta > 1.2 else "bg-amber-50 text-amber-700 border border-amber-200")
    kpis += _kpi_card(
        "Beta 系統風險", _f(beta),
        "Beta>1=高波動 | Beta<1=防御",
        beta_lbl, beta_cls, f"Beta {_f(beta)}", beta_badge
    )
    # MACD
    macd_lbl = "多頭" if macd > 0 else "空頭"
    macd_cls = "text-emerald-600" if macd > 0 else "text-red-600"
    macd_badge= "bg-emerald-50 text-emerald-700 border border-emerald-200" if macd > 0 else "bg-red-50 text-red-700 border border-red-200"
    kpis += _kpi_card(
        "MACD 動量", _f(macd),
        "正=多頭 | 負=空頭",
        macd_lbl, macd_cls, macd_lbl, macd_badge
    )

    return f"""
<!-- ═══════════════════════════════════════════════ PART 2: KPI DECK ══ -->
<section id="kpi" class="bg-[var(--bg)] border-b border-[#E5E3DC]">
    <div class="max-w-7xl mx-auto px-5 py-10">
        <div class="flex items-center gap-3 mb-6">
            <span class="section-label">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
                Executive KPI Deck
            </span>
            <span class="text-xs text-[#8A8A8A]">8 項核心指標</span>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-4">
            {kpis}
        </div>
    </div>
</section>"""


def _build_visual_insights(data, analysts):
    ticker  = data.get("stock","UNKNOWN")
    price   = float(data.get("price", 0))
    targets = data.get("target_prices", {})
    stops   = data.get("stop_losses", {})
    vol     = float(data.get("volatility", 0))
    var95   = abs(float(data.get("var_95", 0)))
    mdd     = abs(float(data.get("max_drawdown", 0)))
    sharpe  = float(data.get("sharpe", 0))

    # v5.8: 委派給 stock_analysis.currency_symbol() 純函數（dedup 第 2 處）
    from stock_analysis import currency_symbol as _currency_symbol_fn
    _currency = data.get("currency", "USD")
    _currency_symbol = _currency_symbol_fn(_currency)

    r_labels = [_analyst_name(r) for r in analysts.keys()]
    r_scores = [float(v.get("score", 0))*100 for v in analysts.values()]
    r_colors = ANALYST_COLORS[:len(analysts)]

    radar_js = (
        "new Chart(document.getElementById('radarChart'),{"
        "type:'radar',"
        "data:{"
        "labels:" + json.dumps(r_labels, ensure_ascii=False) + ","
        "datasets:[{"
        "label:'Analyst Scores',"
        "data:" + json.dumps(r_scores) + ","
        "fill:true,"
        "backgroundColor:'rgba(37,99,235,0.08)',"
        "borderColor:'rgba(37,99,235,0.7)',"
        "pointBackgroundColor:" + json.dumps(r_colors) + ","
        "pointBorderColor:'#fff',"
        "pointRadius:5,pointHoverRadius:7,"
        "borderWidth:2"
        "}]"
        "},"
        "options:{"
        "responsive:true,maintainAspectRatio:true,"
        "scales:{"
        "r:{"
        "min:0,max:100,"
        "ticks:{stepSize:20,font:{size:9},backdropColor:'transparent',color:'#8A8A8A'},"
        "grid:{color:'rgba(0,0,0,0.06)'},"
        "angleLines:{color:'rgba(0,0,0,0.06)'},"
        "pointLabels:{font:{size:10,weight:'500'},color:'#1A1A1A'}"
        "}"
        "},"
        "plugins:{"
        "legend:{display:false},"
        "tooltip:{callbacks:{label:function(ctx){return ctx.label+': '+ctx.raw.toFixed(1)+'/100';}}}"
        "}"
        "});"
    )

    price_js = (
        "async function loadPriceHistory(){"
        "try{"
        "var t='"+ticker+"';"
        "var resp=await fetch('https://query1.finance.yahoo.com/v8/finance/chart/'+t+'?interval=1wk&range=1y');"
        "var j=await resp.json();"
        "var r=j?.chart?.result?.[0];"
        "if(!r){document.getElementById('priceChart').style.display='none';return;}"
        "var ts=r.timestamp||[];"
        "var q=r.indicators?.quote?.[0]||{};"
        "var highs=q.high||[];var lows=q.low||[];var opens=q.open||[];var closes=q.close||[];"
        "var lbls=ts.map(function(t){return new Date(t*1000).toLocaleDateString('zh-TW',{month:'short',day:'numeric'});});"
        "var ctx=document.getElementById('priceChart');"
        "if(!ctx)return;"
        "new Chart(ctx,{"
        "type:'line',"
        "data:{"
        "labels:lbls,"
        "datasets:[{"
        "label:'收盤價 ("+_currency_symbol+")',"
        "data:closes.map(function(c,i){return c?{x:i,y:c}:null;}).filter(Boolean),"
        "borderColor:'#2563EB',backgroundColor:'rgba(37,99,235,0.06)',"
        "fill:true,tension:0.3,pointRadius:2,pointHoverRadius:5,borderWidth:2"
        "}]"
        "},"
        "options:{"
        "responsive:true,maintainAspectRatio:false,"
        "interaction:{mode:'index',intersect:false},"
        "scales:{"
        "x:{display:false},"
        "y:{ticks:{callback:function(v){return'"+_currency_symbol+"'+v.toFixed(0);},color:'#8A8A8A',font:{size:10}},grid:{color:'rgba(0,0,0,0.04)'}}"
        "},"
        "plugins:{"
        "legend:{display:false},"
        "tooltip:{"
        "callbacks:{"
        "label:function(ctx){return'"+_currency_symbol+"'+ctx.raw.y.toFixed(2);},"
        "afterLabel:function(ctx){var i=ctx.raw.x;return'O:"+_currency_symbol+"'+(opens[i]||0).toFixed(2)+' H:"+_currency_symbol+"'+(highs[i]||0).toFixed(2)+' L:"+_currency_symbol+"'+(lows[i]||0).toFixed(2);}"
        "}"
        "}"
        "}"
        "});"
        "}catch(e){"
        "document.getElementById('priceChart').innerHTML='<div class=flex items-center justify-center h-full text-[#8A8A8A] text-sm>圖表載入失敗</div>';"
        "}"
        "}"
        "loadPriceHistory();"
    )

    risk_js = (
        "new Chart(document.getElementById('riskChart'),{"
        "type:'bar',"
        "data:{"
        "labels:['波動性(%)','VaR 95%','MaxDD(%)','Sharpe×10'],"
        "datasets:[{"
        "label:'Value',"
        "data:["+str(vol)+","+str(var95)+","+str(mdd)+","+str(abs(sharpe)*10)+"],"
        "backgroundColor:['rgba(245,158,11,0.7)','rgba(239,68,68,0.7)','rgba(239,68,68,0.5)','rgba(16,185,129,0.7)'],"
        "borderColor:['#F59E0B','#EF4444','#EF4444','#10B981'],"
        "borderWidth:1.5,borderRadius:6"
        "}]"
        "},"
        "options:{"
        "responsive:true,maintainAspectRatio:false,"
        "scales:{"
        "y:{beginAtZero:true,ticks:{callback:function(v){return v.toFixed(0)+'%';},color:'#8A8A8A',font:{size:10}},grid:{color:'rgba(0,0,0,0.04)'}},"
        "x:{ticks:{color:'#8A8A8A',font:{size:10}},grid:{display:false}}"
        "},"
        "plugins:{"
        "legend:{display:false},"
        "tooltip:{callbacks:{label:function(ctx){return ctx.parsed.y.toFixed(2)+'%';},afterLabel:function(ctx){var ls=['年化波動性','單日最大損失(VaR)','歷史最大跌幅','Sharpe×10'];return ls[ctx.dataIndex];}}}"
        "}"
        "});"
    )

    cats    = ["現價","短(1-4W)","中(1-6M)","長(6-12M)"]
    tprices = [price, targets.get("short_term",price), targets.get("mid_term",price), targets.get("long_term",price)]
    sprices = [0, stops.get("short_term",0), stops.get("mid_term",0), stops.get("long_term",0)]
    target_js = (
        "new Chart(document.getElementById('targetChart'),{"
        "type:'bar',"
        "data:{"
        "labels:" + json.dumps(cats, ensure_ascii=False) + ","
        "datasets:["
        "{label:'目標價',data:"+json.dumps(tprices)+","
        "backgroundColor:t=>t.dataIndex===0?'rgba(37,99,235,0.7)':'rgba(16,185,129,0.75)',"
        "borderColor:t=>t.dataIndex===0?'rgba(37,99,235,1)':'rgba(16,185,129,1)',"
        "borderWidth:1.5,borderRadius:6},"
        "{label:'止損價',data:"+json.dumps(sprices)+","
        "backgroundColor:'rgba(239,68,68,0.35)',borderColor:'rgba(239,68,68,0.85)',"
        "borderWidth:1.5,borderRadius:6}"
        "]"
        "},"
        "options:{"
        "responsive:true,maintainAspectRatio:false,"
        "scales:{"
        "y:{beginAtZero:false,ticks:{callback:function(v){return'"+_currency_symbol+"'+v.toFixed(0);},color:'#8A8A8A',font:{size:10}},grid:{color:'rgba(0,0,0,0.04)'}},"
        "x:{ticks:{color:'#8A8A8A',font:{size:10}},grid:{display:false}}"
        "},"
        "plugins:{"
        "legend:{position:'bottom',labels:{font:{size:11},color:'#1A1A1A'}},"
        "tooltip:{"
        "callbacks:{"
        "label:function(ctx){return ctx.dataset.label+': "+_currency_symbol+"'+ctx.raw.toFixed(2);},"
        "afterLabel:function(ctx){"
        "if(ctx.datasetIndex===0&&ctx.dataIndex>0){"
        "var diff=ctx.raw-"+str(price)+";"
        "var pct=(diff/"+str(price)+"*100).toFixed(1);"
        "return(diff>=0?'+':'')+'"+_currency_symbol+"'+Math.abs(diff).toFixed(1)+' ('+pct+'%)';"
        "}return'';"
        "}"
        "}"
        "}"
        "});"
    )

    return f"""
<!-- ══════════════════════════════════════════════ PART 3: VISUAL ══ -->
<section id="visual" class="bg-[var(--bg)] border-b border-[#E5E3DC]">
    <div class="max-w-7xl mx-auto px-5 py-10 space-y-8">
        <div class="flex items-center gap-3">
            <span class="section-label">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                Visual Insights
            </span>
        </div>
        <!-- Row 1: Price + Radar -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="lg:col-span-2 card p-5">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-sm font-bold text-[#1A1A1A] flex items-center gap-2">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                        價格歷史 (1年期)
                    </h3>
                    <span class="text-xs text-[#8A8A8A]">Yahoo Finance 實時數據</span>
                </div>
                <div style="height:240px;position:relative"><canvas id="priceChart"></canvas></div>
            </div>
            <div class="card p-5">
                <h3 class="text-sm font-bold text-[#1A1A1A] mb-4 flex items-center gap-2">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                    7維分析師評分
                </h3>
                <div style="max-height:260px"><canvas id="radarChart"></canvas></div>
            </div>
        </div>
        <!-- Row 2: Risk + Target -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="card p-5">
                <h3 class="text-sm font-bold text-[#1A1A1A] mb-4 flex items-center gap-2">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#DC2626" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    風險指標
                </h3>
                <div style="height:200px"><canvas id="riskChart"></canvas></div>
            </div>
            <div class="card p-5">
                <h3 class="text-sm font-bold text-[#1A1A1A] mb-4 flex items-center gap-2">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>
                    目標價 vs 止損
                </h3>
                <div style="height:200px"><canvas id="targetChart"></canvas></div>
            </div>
        </div>
    </div>
</section>

<script>
{price_js}
</script>
<script>
{radar_js}
{risk_js}
{target_js}
</script>"""


def _build_analyst_section(analysts, analyst_text, ws, consensus_s, conf):
    conf_l, conf_c = _conf_label(conf)
    cards = ""
    for role in ["market","technical","fundamental","risk","sentiment","news","macro"]:
        info   = analysts.get(role, {})
        atext  = (analyst_text or {}).get(role, {})
        score  = float(info.get("score", 0))
        signal = info.get("signal", "neutral")
        pct_v  = min(score * 100, 100)
        conf_l2, conf_c2 = _conf_label(score)

        argument   = atext.get("argument","") or ""
        evidence   = atext.get("evidence","") or ""
        ds         = atext.get("data_source","") or ""
        conclusion = atext.get("conclusion","") or ""
        if isinstance(argument, list):   argument   = " | ".join(str(x) for x in argument)
        if isinstance(evidence, list):   evidence   = " | ".join(str(x) for x in evidence)
        if isinstance(ds, list):         ds         = " | ".join(str(x) for x in ds)
        if isinstance(conclusion, list):  conclusion = " | ".join(str(x) for x in conclusion)

        sig_cls = "signal-buy" if signal.lower()=="buy" else "signal-sell" if signal.lower()=="sell" else "signal-hold"
        icon_bg = ["#EFF6FF","#F5F3FF","#ECFDF5","#FFFBEB","#FDF2F8","#ECFEFF","#FFF7ED"][
            ["market","technical","fundamental","risk","sentiment","news","macro"].index(role) if role in ["market","technical","fundamental","risk","sentiment","news","macro"] else 0]
        icon_fg = ["#2563EB","#7C3AED","#059669","#D97706","#DB2777","#0891B2","#EA580C"][
            ["market","technical","fundamental","risk","sentiment","news","macro"].index(role) if role in ["market","technical","fundamental","risk","sentiment","news","macro"] else 0]

        # Accordion body content
        body_content = ""
        if ds:
            body_content += f'<div class="mb-3"><div class="text-[10px] font-bold text-[#2563EB] mb-1 flex items-center gap-1"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg> 數據來源</div><p class="text-xs text-[#4A4A4A] leading-relaxed">{_e(str(ds)[:200]) if ds else "—"}</p></div>'
        if argument:
            body_content += f'<div class="mb-3"><div class="text-[10px] font-bold text-[#1A1A1A] mb-1 flex items-center gap-1"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 14 18.469V19a2 2 0 1 1-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg> 核心論點</div><p class="text-xs text-[#1A1A1A] leading-relaxed">{_e(str(argument)[:500]) if argument else "—"}</p></div>'
        if evidence:
            body_content += f'<div class="mb-3"><div class="text-[10px] font-bold text-[#1A1A1A] mb-1 flex items-center gap-1"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg> 關鍵證據</div><p class="text-xs text-[#4A4A4A] leading-relaxed">{_e(str(evidence)[:300]) if evidence else "—"}</p></div>'
        if conclusion:
            body_content += f'<div><div class="text-[10px] font-bold text-[#1A1A1A] mb-1 flex items-center gap-1"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg> 評估結論</div><p class="text-xs text-[#1A1A1A] leading-relaxed">{_e(str(conclusion)[:200]) if conclusion else "—"}</p></div>'

        cards += f"""
        <div class="accordion-item" data-role="{role}">
            <div class="accordion-header" onclick="this.parentElement.classList.toggle('open')">
                <div class="w-10 h-10 rounded-xl flex items-center justify-center text-xs font-black flex-shrink-0" style="background:{icon_bg};color:{icon_fg}">{_analyst_icon(role)}</div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-0.5">
                        <h4 class="font-bold text-[#1A1A1A] text-sm">{_analyst_name(role)}</h4>
                        <span class="{sig_cls} text-[10px] font-bold px-2 py-0.5 rounded-full">{signal.upper()}</span>
                    </div>
                    <p class="text-[10px] text-[#8A8A8A]">{ANALYST_META.get(role,"")}</p>
                </div>
                <div class="flex items-center gap-3 flex-shrink-0">
                    <div class="text-right">
                        <div class="text-lg font-black text-[#1A1A1A] leading-none">{_f(score)}</div>
                        <div class="text-[10px] {conf_c2} font-semibold">{conf_l2}</div>
                    </div>
                    <div class="w-20 h-2 bg-[#F1F0EC] rounded-full overflow-hidden">
                        <div class="{_score_bg(score)} h-2 rounded-full transition-all" style="width:{pct_v}%"></div>
                    </div>
                    <svg class="accordion-chevron text-[#8A8A8A]" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                </div>
            </div>
            <div class="accordion-body">
                <div class="pt-4">{body_content}</div>
            </div>
        </div>"""

    return f"""
<!-- ═══════════════════════════════════════════ PART 4: ANALYSTS ══ -->
<section id="analysts" class="bg-[var(--bg)] border-b border-[#E5E3DC]">
    <div class="max-w-7xl mx-auto px-5 py-10">
        <div class="flex items-center gap-3 mb-6 flex-wrap">
            <span class="section-label">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                7位專業分析師
            </span>
            <span class="badge-blue text-xs font-bold px-3 py-1 rounded-xl">加權評分: <span class="{_score_color(ws)} font-black">{_f(ws)}</span></span>
            <span class="badge-purple text-xs font-bold px-3 py-1 rounded-xl">共識: {consensus_s.upper()}</span>
            <span class="text-xs text-[#8A8A8A]">置信度: <span class="{conf_c} font-bold">{_f(conf)} ({conf_l})</span></span>
        </div>
        <div class="space-y-2">{cards}</div>
    </div>
</section>"""


def _build_narrative_section(analysts, analyst_text, ws, consensus_s, conf):
    """Deep narrative / 深度解讀 — collapsed by default, shows key insights."""
    conf_l, conf_c = _conf_label(conf)
    insights = []
    for role in ["market","technical","fundamental","risk","sentiment","news","macro"]:
        atext  = (analyst_text or {}).get(role, {})
        info   = analysts.get(role, {})
        score  = float(info.get("score", 0))
        signal = info.get("signal", "neutral")
        conclusion = atext.get("conclusion","") or ""
        if isinstance(conclusion, list): conclusion = " | ".join(str(x) for x in conclusion)
        if conclusion:
            sig_icon = "🟢" if signal.lower()=="buy" else ("🔴" if signal.lower()=="sell" else "🟡")
            insights.append(f"<strong>{_analyst_name(role)}</strong>: {_e(str(conclusion)[:200])}")

    if not insights:
        return ""

    insight_items = "".join(f'<li class="text-sm text-[#4A4A4A] leading-relaxed">{i}</li>' for i in insights)

    return f"""
<!-- ══════════════════════════════════════════ PART: NARRATIVE ══ -->
<section id="narrative" class="bg-[var(--bg)] border-b border-[#E5E3DC]">
    <div class="max-w-7xl mx-auto px-5 py-10">
        <div class="flex items-center gap-3 mb-6">
            <span class="section-label">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                深度解讀
            </span>
        </div>
        <div class="card p-6">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div class="text-center p-4 bg-[#F1F0EC] rounded-xl">
                    <div class="text-3xl font-black text-[#1A1A1A]">{_f(ws)}<span class="text-sm font-normal text-[#8A8A8A]">/1.00</span></div>
                    <div class="text-[10px] text-[#8A8A8A] uppercase tracking-widest mt-1">加權評分</div>
                </div>
                <div class="text-center p-4 bg-[#F1F0EC] rounded-xl">
                    <div class="text-3xl font-black text-[#1A1A1A]">{consensus_s.upper()}</div>
                    <div class="text-[10px] text-[#8A8A8A] uppercase tracking-widest mt-1">共識信號</div>
                </div>
                <div class="text-center p-4 bg-[#F1F0EC] rounded-xl">
                    <div class="text-3xl font-black {conf_c}">{_f(conf)}</div>
                    <div class="text-[10px] text-[#8A8A8A] uppercase tracking-widest mt-1">置信度 ({conf_l})</div>
                </div>
            </div>
            <div class="border-t border-[#E5E3DC] pt-5">
                <h3 class="text-sm font-bold text-[#1A1A1A] mb-4 flex items-center gap-2">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                    分析師關鍵結論
                </h3>
                <ul class="space-y-3">{insight_items}</ul>
            </div>
        </div>
    </div>
</section>"""


def _build_debate_section(debate_log, debate_consensus, analysts):
    if not debate_log:
        return ""

    rounds = {}
    for e in debate_log:
        rounds.setdefault(e.get("round",0), []).append(e)

    TYPE_ICONS = {
        "argument":"📢","challenge":"❓","counter":"🔄","concede":"👍",
        "compromise":"🤝","support":"💪","warning":"⚠️","observation":"👁️",
        "analysis":"📊","data":"📈","summary":"📋","final":"🏁"
    }
    TYPE_CLASS = {
        "argument":"debate-argument","challenge":"debate-challenge",
        "counter":"debate-counter","concede":"debate-concede","warning":"debate-warning"
    }

    debate_html = ""
    for rnd in sorted(rounds.keys()):
        debate_html += f'<div class="mb-6"><div class="flex items-center gap-2 mb-3"><span class="w-6 h-6 rounded-full bg-[#2563EB] flex items-center justify-center text-[10px] font-black text-white">{rnd}</span><span class="font-bold text-sm text-[#1A1A1A]">第 {rnd} 輪辯論</span><span class="flex-1 h-px bg-[#E5E3DC]"></span></div><div class="space-y-2">'
        for e in rounds[rnd]:
            icon    = TYPE_ICONS.get(e.get("type","argument"),"•")
            cls     = TYPE_CLASS.get(e.get("type",""),"debate-argument")
            fm      = _e(e.get("from","?"))
            to      = _e(e.get("to","?"))
            content = e.get("content", {})
            arg_txt = content.get("argument") or content.get("challenge") or content.get("observation") or content.get("analysis") or ""
            ev_txt  = content.get("evidence","")
            conc_txt= content.get("concession","")
            adj     = content.get("adjustment")
            is_llm  = content.get("LLM_GENERATED") or content.get("llm_generated")
            if isinstance(arg_txt, list): arg_txt = " | ".join(str(x) for x in arg_txt)
            if isinstance(ev_txt, list):  ev_txt   = " | ".join(str(x) for x in ev_txt)
            lbl_llm = '<span class="ml-auto text-[10px] bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full font-bold">LLM</span>' if is_llm else ''

            debate_html += f"""<div class="bg-white rounded-xl p-4 border border-[#E5E3DC] {cls} text-sm">
                <div class="flex items-center gap-2 mb-2">
                    <span class="text-base">{icon}</span>
                    <span class="font-bold text-[#2563EB] text-xs">{fm}</span>
                    <span class="text-[#8A8A8A] text-xs">→</span>
                    <span class="font-bold text-[#7C3AED] text-xs">{to}</span>
                    {lbl_llm}
                </div>"""
            if arg_txt: debate_html += f'<p class="text-[#1A1A1A] text-xs leading-relaxed pl-7">{_e(str(arg_txt)[:500])}</p>'
            if ev_txt:  debate_html += f'<p class="text-[#4A4A4A] text-xs leading-relaxed pl-7 mt-1"><span class="font-semibold text-[#1A1A1A]">📊:</span> {_e(str(ev_txt)[:200])}</p>'
            if conc_txt:debate_html += f'<p class="text-emerald-600 text-xs leading-relaxed pl-7 mt-1"><span class="font-semibold">👍:</span> {_e(str(conc_txt)[:200])}</p>'
            if adj is not None:
                sign = "+" if adj > 0 else ""
                debate_html += f'<p class="text-blue-600 text-xs leading-relaxed pl-7 mt-1"><span class="font-semibold">調整:</span> {sign}{_f(adj)}</p>'
            debate_html += "</div>"
        debate_html += "</div></div>"

    bull   = debate_consensus.get("bull_case","") or debate_consensus.get("bullish_case","")
    bear   = debate_consensus.get("bear_case","") or debate_consensus.get("bearish_case","")
    themes = debate_consensus.get("main_themes",[])
    dissent= debate_consensus.get("dissenting_views",[])
    conf_d = float(debate_consensus.get("confidence", 0))
    csig   = debate_consensus.get("consensus_signal","hold")
    conf_l, conf_c = _conf_label(conf_d)

    cons_html = ""
    if bull:
        cons_html += '<div class="bg-emerald-50 border border-emerald-200 rounded-xl p-4 mb-3"><div class="text-[10px] font-bold text-emerald-700 mb-1">🟢 BULL CASE</div><p class="text-sm text-emerald-800 leading-relaxed">'+_e(str(bull)[:400])+'</p></div>'
    if bear:
        cons_html += '<div class="bg-red-50 border border-red-200 rounded-xl p-4 mb-3"><div class="text-[10px] font-bold text-red-700 mb-1">🔴 BEAR CASE</div><p class="text-sm text-red-800 leading-relaxed">'+_e(str(bear)[:400])+'</p></div>'
    if themes:
        t_str = " | ".join(str(t) for t in themes) if isinstance(themes,list) else str(themes)
        cons_html += '<div class="bg-[#F1F0EC] rounded-xl p-4 mb-3"><div class="text-[10px] font-bold text-[#1A1A1A] mb-1">📌 主要主題</div><p class="text-sm text-[#4A4A4A] leading-relaxed">'+_e(t_str[:300])+'</p></div>'
    if dissent:
        d_str = " | ".join(str(d) for d in dissent) if isinstance(dissent,list) else str(dissent)
        cons_html += '<div class="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-3"><div class="text-[10px] font-bold text-amber-700 mb-1">⚔️ 分歧意見</div><p class="text-sm text-amber-800 leading-relaxed">'+_e(d_str[:300])+'</p></div>'

    evo_rows = ""
    for role, info in analysts.items():
        score = float(info.get("final_score", 0))
        conc  = info.get("concessions", 0)
        sig   = info.get("signal","neutral")
        conf_l2, conf_c2 = _conf_label(score)
        sig_cls = "signal-buy" if sig.lower()=="buy" else "signal-sell" if sig.lower()=="sell" else "signal-hold"
        icon_bg = ["#EFF6FF","#F5F3FF","#ECFDF5","#FFFBEB","#FDF2F8","#ECFEFF","#FFF7ED"][
            ["market","technical","fundamental","risk","sentiment","news","macro"].index(role) if role in ["market","technical","fundamental","risk","sentiment","news","macro"] else 0]
        icon_fg = ["#2563EB","#7C3AED","#059669","#D97706","#DB2777","#0891B2","#EA580C"][
            ["market","technical","fundamental","risk","sentiment","news","macro"].index(role) if role in ["market","technical","fundamental","risk","sentiment","news","macro"] else 0]
        evo_rows += (
            '<tr class="border-b border-[#F1F0EC] hover:bg-[#F8F7F4] transition-colors">'
            '<td class="py-3 px-3"><div class="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-black" style="background:'+icon_bg+';color:'+icon_fg+'">'+_analyst_icon(role)+'</div></td>'
            '<td class="py-3 px-3 text-sm font-medium text-[#1A1A1A]">'+_analyst_name(role)+'</td>'
            '<td class="py-3 px-3"><span class="'+sig_cls+' text-[10px] font-bold px-2 py-0.5 rounded-full">'+sig.upper()+'</span></td>'
            '<td class="py-3 px-3"><span class="'+conf_c2+' font-black text-base">'+_f(score)+'</span></td>'
            '<td class="py-3 px-3 text-center text-[#8A8A8A] text-xs">'+str(conc)+'</td>'
            '</tr>'
        )

    return f"""
<!-- ═════════════════════════════════════════════ PART: DEBATE ══ -->
<section id="debate" class="bg-[var(--bg)] border-b border-[#E5E3DC]">
    <div class="max-w-7xl mx-auto px-5 py-10">
        <div class="flex items-center gap-3 mb-6 flex-wrap">
            <span class="section-label">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                LLM 辯論記錄
            </span>
            <span class="badge-purple text-xs font-bold px-3 py-1 rounded-xl">共識: <span class="{conf_c}">{csig.upper()}</span></span>
            <span class="text-xs text-[#8A8A8A]">置信度: <span class="{conf_c} font-bold">{_f(conf_d)} ({conf_l})</span></span>
        </div>
        {cons_html}
        <!-- Score evolution -->
        <div class="card overflow-hidden mb-6">
            <div class="px-5 py-4 border-b border-[#E5E3DC]">
                <h3 class="text-sm font-bold text-[#1A1A1A]">評分演變 (INITIAL → FINAL)</h3>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-sm min-w-[500px]">
                    <thead>
                        <tr class="border-b border-[#E5E3DC] bg-[#F8F7F4]">
                            <th class="text-left py-2.5 px-3 text-[10px] text-[#8A8A8A] font-bold uppercase tracking-wider">代號</th>
                            <th class="text-left py-2.5 px-3 text-[10px] text-[#8A8A8A] font-bold uppercase tracking-wider">分析師</th>
                            <th class="text-left py-2.5 px-3 text-[10px] text-[#8A8A8A] font-bold uppercase tracking-wider">信號</th>
                            <th class="text-left py-2.5 px-3 text-[10px] text-[#8A8A8A] font-bold uppercase tracking-wider">最終評分</th>
                            <th class="text-center py-2.5 px-3 text-[10px] text-[#8A8A8A] font-bold uppercase tracking-wider">讓步次</th>
                        </tr>
                    </thead>
                    <tbody>{evo_rows}</tbody>
                </table>
            </div>
        </div>
        <div class="space-y-1">{debate_html}</div>
    </div>
</section>"""


def _build_news_section(news_items, sentiment_lbl):
    if not news_items:
        return '<section id="news" class="bg-[var(--bg)] border-b border-[#E5E3DC]"><div class="max-w-7xl mx-auto px-5 py-10"><div class="card p-8 text-center"><p class="text-[#8A8A8A]">暫無新聞數據</p></div></div></section>'

    items_html = ""
    for n in news_items[:20]:
        sent   = n.get("sentiment","")
        title  = _e(n.get("title",""))
        source = _e(n.get("source","")[:12])
        url    = n.get("url","")
        sent_c = _sentiment_color(sent)
        sent_bg= "bg-emerald-50" if "positive" in sent.lower() or "buy" in sent.lower() or "bull" in sent.lower() else ("bg-red-50" if "negative" in sent.lower() or "sell" in sent.lower() or "bear" in sent.lower() else "bg-amber-50")
        title_html = title if not url else f'<a href="{_e(url)}" target="_blank" class="text-[#2563EB] hover:text-[#1D4ED8] hover:underline">{title}</a>'
        items_html += (
            f'<div class="news-item">'
            f'<div class="w-16 flex-shrink-0 text-center">'
            f'<div class="text-[10px] font-bold text-[#8A8A8A] bg-[#F1F0EC] px-2 py-1 rounded-lg border border-[#E5E3DC]">{source}</div>'
            f'</div>'
            f'<div class="flex-1 min-w-0">'
            f'<div class="text-sm text-[#1A1A1A] leading-snug mb-1">{title_html}</div>'
            f'<span class="{sent_bg} {sent_c} text-[10px] font-bold px-2 py-0.5 rounded-full">{_e(sent)}</span>'
            f'</div></div>'
        )

    return f"""
<!-- ══════════════════════════════════════════════ PART: NEWS ══ -->
<section id="news" class="bg-[var(--bg)] border-b border-[#E5E3DC]">
    <div class="max-w-7xl mx-auto px-5 py-10">
        <div class="flex items-center gap-3 mb-6 flex-wrap">
            <span class="section-label">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/></svg>
                最新新聞 TOP 20
            </span>
            <span class="text-xs text-[#8A8A8A]">共 {len(news_items)} 條</span>
            <span class="{_sentiment_color(sentiment_lbl)} text-xs font-bold px-2 py-0.5 rounded-full bg-[#F1F0EC] border border-[#E5E3DC]">情緒: {sentiment_lbl}</span>
        </div>
        <div class="card overflow-hidden">{items_html}</div>
    </div>
</section>"""


def _build_risk_section(data, bt_html, pos_html):
    vol    = float(data.get("volatility", 0))
    var95  = abs(float(data.get("var_95", 0)))
    mdd    = abs(float(data.get("max_drawdown", 0)))
    sharpe = float(data.get("sharpe", 0))
    beta   = float(data.get("beta", 1))

    sharpe_cls = "text-emerald-600" if sharpe > 1 else ("text-red-600" if sharpe < 0 else "text-amber-600")
    beta_cls   = "text-emerald-600" if beta < 0.8 else ("text-red-600" if beta > 1.2 else "text-amber-600")

    return f"""
<!-- ══════════════════════════════════════════════ PART: RISK ══ -->
<section id="risk" class="bg-[var(--bg)] border-b border-[#E5E3DC]">
    <div class="max-w-7xl mx-auto px-5 py-10">
        <div class="flex items-center gap-3 mb-6">
            <span class="section-label">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                風險評估
            </span>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div class="card p-5 text-center">
                <div class="text-3xl font-black text-red-600">{_pct(var95)}</div>
                <div class="text-[10px] text-[#8A8A8A] mt-2 font-semibold">VaR (95%)</div>
                <div class="text-[10px] text-[#8A8A8A]">單日5%概率最大損失</div>
            </div>
            <div class="card p-5 text-center">
                <div class="text-3xl font-black text-red-600">{_pct(mdd)}</div>
                <div class="text-[10px] text-[#8A8A8A] mt-2 font-semibold">最大回撤</div>
                <div class="text-[10px] text-[#8A8A8A]">歷史最大跌幅</div>
            </div>
            <div class="card p-5 text-center">
                <div class="text-3xl font-black {sharpe_cls}">{_f(sharpe)}</div>
                <div class="text-[10px] text-[#8A8A8A] mt-2 font-semibold">Sharpe Ratio</div>
                <div class="text-[10px] text-[#8A8A8A]">理想 &gt; 1.0</div>
            </div>
            <div class="card p-5 text-center">
                <div class="text-3xl font-black {beta_cls}">{_f(beta)}</div>
                <div class="text-[10px] text-[#8A8A8A] mt-2 font-semibold">Beta</div>
                <div class="text-[10px] text-[#8A8A8A]">系統風險系數</div>
            </div>
        </div>
        {bt_html}
        {pos_html}
    </div>
</section>"""


def _build_technical_section(data):
    raw = json.dumps(data, indent=2, ensure_ascii=False)
    return f"""
<!-- ═══════════════════════════════════════════ PART 5: TECHNICAL ══ -->
<section id="technical" class="bg-[var(--bg)]">
    <div class="max-w-7xl mx-auto px-5 py-10">
        <div class="flex items-center gap-3 mb-6">
            <span class="section-label">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>
                Technical Traceability
            </span>
        </div>
        <div class="card overflow-hidden">
            <details class="group">
                <summary class="cursor-pointer p-5 text-sm font-bold text-[#1A1A1A] hover:bg-[#F8F7F4] transition-colors list-none flex items-center justify-between">
                    <span class="flex items-center gap-2">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>
                        底層數據與計算方法論
                    </span>
                    <span class="text-[#8A8A8A] text-xs group-open:rotate-180 transition-transform">▼</span>
                </summary>
                <div class="px-5 pb-5 border-t border-[#E5E3DC] space-y-4">
                    <div>
                        <h4 class="text-xs font-bold text-[#8A8A8A] mb-2 uppercase tracking-wider">計算方法</h4>
                        <ul class="text-xs text-[#4A4A4A] space-y-1">
                            <li>• <strong class="text-[#1A1A1A]">加權評分:</strong> market=0.12, technical=0.18, fundamental=0.22, risk=0.15, sentiment=0.18, news=0.07, macro=0.08</li>
                            <li>• <strong class="text-[#1A1A1A]">共識信號:</strong> weighted ≥0.6 = buy | 0.4–0.6 = hold | &lt;0.4 = sell</li>
                            <li>• <strong class="text-[#1A1A1A]">置信度:</strong> High≥0.7 | Med 0.45–0.7 | Low&lt;0.45</li>
                            <li>• <strong class="text-[#1A1A1A]">數據來源:</strong> Finnhub即時報價 + yfinance歷史數據 + Google News RSS情緒</li>
                        </ul>
                    </div>
                    <div>
                        <button onclick="copyRaw()" class="bg-[#2563EB] text-white text-xs px-4 py-2 rounded-lg hover:bg-[#1D4ED8] transition-colors font-bold">
                            📋 複製 JSON 原始數據
                        </button>
                    </div>
                    <div class="hidden" id="rawJsonData">{_e(raw)}</div>
                    <pre class="bg-[#F8F7F4] text-[#4A4A4A] text-xs p-4 rounded-xl overflow-x-auto border border-[#E5E3DC] max-h-80 leading-relaxed">{_e(raw)}</pre>
                </div>
            </details>
        </div>
    </div>
</section>

<script>
function copyRaw() {{
    var txt = document.getElementById('rawJsonData').textContent;
    navigator.clipboard.writeText(txt).then(function() {{
        var btn = event.target;
        btn.textContent = '✅ 已複製！';
        setTimeout(function(){{ btn.textContent = '📋 複製 JSON 原始數據'; }}, 2000);
    }}).catch(function(){{ alert('複製失敗'); }});
}}
</script>"""


# ─────────────────────────────────────────────────────────────────────────────
# Main generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_html_report(data: Dict[str, Any], output_dir: str) -> str:
    ticker        = data.get("stock","UNKNOWN")
    name          = data.get("stock_name","Unknown")
    analysis_time = data.get("analysis_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    os.makedirs(output_dir, exist_ok=True)

    safe_ticker = ticker.replace(".","_").replace(":","_")
    safe_name   = "".join(c if c.isalnum() or c in " -_" else "_" for c in name)
    html_path   = os.path.join(output_dir, f"{safe_ticker}_{safe_name}_v5.html")

    analysts      = data.get("analysts", {})
    analyst_text  = data.get("analyst_text", {})
    ws            = float(data.get("weighted_score", 0))
    consensus_s   = data.get("consensus_signal","hold")
    confidence    = float(data.get("confidence", 0))
    debate_log    = data.get("debate_log", [])
    debate_cons   = data.get("debate_consensus", {})
    debate_analysts = data.get("debate_analysts", analysts)
    news_items    = data.get("news_items", [])
    sentiment_lbl = data.get("sentiment","neutral")

    # v5.2: 數學共識（ConsensusEngine）— 若有，從 data.math_consensus 提取
    math_consensus = data.get("math_consensus", {}) or {}
    if isinstance(math_consensus, dict) and math_consensus.get("consensus"):
        _mc = math_consensus["consensus"]
        _mc_overall = float(_mc.get("overall", 0))  # -100..+100
        _mc_conf = float(math_consensus.get("confidence", 0))
        _mc_5tier_label = math_consensus.get("signal_label", "HOLD")
        _mc_conflict_n = len(math_consensus.get("conflicts", []) or [])
    else:
        _mc_overall = _mc_conf = 0.0
        _mc_5tier_label = "N/A"
        _mc_conflict_n = 0

    # Backtest
    bt_path = data.get("backtest_path", "")
    if not bt_path:
        import glob as _glob
        ticker_for_glob = ticker
        pattern = os.path.expanduser("~/.hermes/stock_backtest/") + ticker_for_glob + "_*.json"
        matches = sorted(_glob.glob(pattern))
        if matches:
            bt_path = matches[-1]
    pos_data    = data.get("position_sizing", {})
    market_data = data.get("market_data", {})

    sig_map = {
        "buy":    f"7位分析師共識給予 BUY 評級，加權分 {_f(ws)}，置信度 {'HIGH' if confidence>=0.7 else 'MEDIUM' if confidence>=0.45 else 'LOW'}",
        "sell":   f"7位分析師共識顯示 SELL 信號，加權分 {_f(ws)}，請謹慎操作",
        "hold":   f"7位分析師共識維持 HOLD 立場，加權分 {_f(ws)}，方向未明，建議觀望",
        "neutral":f"分析師意見分歧，加權分 {_f(ws)}，建議謹慎",
    }
    summary = sig_map.get(consensus_s.lower(), f"加權評分 {_f(ws)}，共識: {consensus_s}")

    bt_html = ""
    if bt_path and os.path.exists(bt_path):
        try:
            with open(bt_path) as f: bt = json.load(f)
            m     = bt.get("metrics", {})
            acc   = float(m.get("overall_accuracy",0))*100
            pbuy  = float(m.get("precision_buy",0))*100
            psell = float(m.get("precision_sell",0))*100
            total = bt.get("effective_predictions",0)
            cnts  = bt.get("signal_counts",{})
            bc,sc,hc = cnts.get("buy",0),cnts.get("sell",0),cnts.get("hold",0)
            bt_html = (
                '<div class="card p-5 mb-4">'
                '<h3 class="text-sm font-bold text-[#1A1A1A] mb-4 flex items-center gap-2">'
                '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2"><path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18"/></svg>'
                '自動回測（過去90天）</h3>'
                '<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">'
                '<div class="bg-[#F1F0EC] rounded-xl p-4 text-center"><div class="text-2xl font-black text-[#1A1A1A]">'+_f(acc,".1f")+'%</div><div class="text-[10px] text-[#8A8A8A] mt-1">整體準確度</div></div>'
                '<div class="bg-emerald-50 rounded-xl p-4 text-center"><div class="text-2xl font-black text-emerald-600">'+_f(pbuy,".1f")+'%</div><div class="text-[10px] text-[#8A8A8A] mt-1">Buy 精準度</div></div>'
                '<div class="bg-red-50 rounded-xl p-4 text-center"><div class="text-2xl font-black text-red-600">'+_f(psell,".1f")+'%</div><div class="text-[10px] text-[#8A8A8A] mt-1">Sell 精準度</div></div>'
                '<div class="bg-[#F1F0EC] rounded-xl p-4 text-center"><div class="text-2xl font-black text-[#1A1A1A]">'+str(total)+'</div><div class="text-[10px] text-[#8A8A8A] mt-1">總預測次數</div></div>'
                '</div>'
                '<div class="text-xs text-[#8A8A8A]">信號分佈: <span class="text-emerald-600 font-semibold">Buy '+str(bc)+'</span> | <span class="text-red-600 font-semibold">Sell '+str(sc)+'</span> | <span class="text-amber-600 font-semibold">Hold '+str(hc)+'</span></div>'
                '</div>'
            )
        except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError, TypeError):
            pass

    pos_html = ""
    if pos_data:
        pos_html = (
            '<div class="card p-5">'
            '<h3 class="text-sm font-bold text-[#1A1A1A] mb-4 flex items-center gap-2">'
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>'
            '倉位計算</h3>'
            '<div class="grid grid-cols-2 md:grid-cols-4 gap-3">'
            '<div class="bg-[#EFF6FF] rounded-xl p-4 text-center"><div class="text-2xl font-black text-[#2563EB]">'+_f(pos_data.get('position_size_pct',0))+'%</div><div class="text-[10px] text-[#8A8A8A] mt-1">倉位比例</div></div>'
            '<div class="bg-emerald-50 rounded-xl p-4 text-center"><div class="text-2xl font-black text-emerald-600">$'+_f(pos_data.get('dollar_amount',0))+'</div><div class="text-[10px] text-[#8A8A8A] mt-1">投入金額</div></div>'
            '<div class="bg-red-50 rounded-xl p-4 text-center"><div class="text-2xl font-black text-red-600">$'+_f(pos_data.get('risk_amount',0))+'</div><div class="text-[10px] text-[#8A8A8A] mt-1">風險金額</div></div>'
            '<div class="bg-[#F1F0EC] rounded-xl p-4 text-center"><div class="text-2xl font-black text-[#1A1A1A]">$'+_f(pos_data.get('account_size',0))+'</div><div class="text-[10px] text-[#8A8A8A] mt-1">帳戶規模</div></div>'
            '</div></div>'
        )

    # v5.2: 數學共識面板（ConsensusEngine 7 因子加權 + 衝突檢測）
    math_consensus_html = ""
    if math_consensus and isinstance(math_consensus, dict) and math_consensus.get("consensus"):
        _mc_cons = math_consensus["consensus"]
        _buy_pct = float(_mc_cons.get("buy", 0))
        _hold_pct = float(_mc_cons.get("hold", 0))
        _sell_pct = float(_mc_cons.get("sell", 0))
        _rec = math_consensus.get("recommendation", "HOLD")
        _rec_cls = "signal-buy" if "buy" in _rec.lower() else "signal-sell" if "sell" in _rec.lower() else "signal-hold"
        _conflict_html = ""
        if _mc_conflict_n > 0:
            _conflict_html = (
                f'<div class="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">'
                f'<div class="text-xs font-bold text-amber-700 flex items-center gap-1">'
                f'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
                f'衝突檢測: {_mc_conflict_n} 個 buy/sell 分歧</div></div>'
            )
        math_consensus_html = (
            '<div class="card p-5 mb-4">'
            '<h3 class="text-sm font-bold text-[#1A1A1A] mb-4 flex items-center gap-2">'
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>'
            '數學共識引擎 (ConsensusEngine v5.1)</h3>'
            '<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">'
            # Buy%
            f'<div class="bg-emerald-50 rounded-xl p-4 text-center"><div class="text-2xl font-black text-emerald-600">{_f(_buy_pct,".1f")}%</div><div class="text-[10px] text-[#8A8A8A] mt-1">買入比例</div></div>'
            # Hold%
            f'<div class="bg-amber-50 rounded-xl p-4 text-center"><div class="text-2xl font-black text-amber-600">{_f(_hold_pct,".1f")}%</div><div class="text-[10px] text-[#8A8A8A] mt-1">持有比例</div></div>'
            # Sell%
            f'<div class="bg-red-50 rounded-xl p-4 text-center"><div class="text-2xl font-black text-red-600">{_f(_sell_pct,".1f")}%</div><div class="text-[10px] text-[#8A8A8A] mt-1">賣出比例</div></div>'
            # Overall score
            f'<div class="bg-[#F5F3FF] rounded-xl p-4 text-center"><div class="text-2xl font-black text-[#7C3AED]">{_mc_overall:+.1f}</div><div class="text-[10px] text-[#8A8A8A] mt-1">整體得分 (-100..+100)</div></div>'
            '</div>'
            '<div class="flex flex-wrap items-center gap-3 text-xs">'
            f'<span class="badge-purple text-xs font-bold px-3 py-1 rounded-xl">5-Tier: {_mc_5tier_label}</span>'
            f'<span class="text-[#8A8A8A]">多因子置信度: <span class="text-[#7C3AED] font-bold">{_f(_mc_conf)}</span></span>'
            f'<span class="text-[#8A8A8A]">LLM 置信度: <span class="text-[#2563EB] font-bold">{_f(confidence)}</span></span>'
            f'<span class="text-[#8A8A8A]">合併: <span class="text-[#1A1A1A] font-bold">{_f(min(_mc_conf, confidence))}</span> (取較保守)</span>'
            '</div>'
            + _conflict_html +
            '</div>'
        )

    header_html   = _build_header(ticker, name, summary, analysis_time, ws, consensus_s, confidence)
    kpi_html      = _build_kpi_deck(data)
    visual_html   = _build_visual_insights(data, analysts)
    analyst_html  = _build_analyst_section(analysts, analyst_text, ws, consensus_s, confidence)
    narrative_html= _build_narrative_section(analysts, analyst_text, ws, consensus_s, confidence)
    debate_html   = _build_debate_section(debate_log, debate_cons, debate_analysts)
    news_html     = _build_news_section(news_items, sentiment_lbl)
    risk_html     = _build_risk_section(data, bt_html, pos_html)
    tech_html     = _build_technical_section(data)

    html = (
        '<!DOCTYPE html>'
        '<html lang="zh-TW">'
        '<head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<title>' + _e(name) + ' (' + ticker + ') - Stock Analysis v5</title>'
        '<script src="' + TAILWIND + '"></script>'
        '<script src="' + CHART_CDN + '"></script>'
        '<style>'
        + OPEN_CSS +
        '</style>'
        '</head>'
        '<body>'
        + header_html +
        '<main class="max-w-7xl mx-auto px-4 py-0"><div class="h-3"></div></main>'
        + kpi_html
        + math_consensus_html
        + visual_html
        + analyst_html
        + narrative_html
        + debate_html
        + news_html
        + risk_html
        + tech_html +
        '<footer class="bg-white border-t border-[#E5E3DC] py-8 text-center no-print">'
        '<div class="text-[#8A8A8A] text-xs">'
        '<p class="font-semibold text-[#4A4A4A]">Stock Team Agent v5 — Generated: ' + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + '</p>'
        '<p class="mt-1">Powered by MiniMax M2.7 + 7 Professional Analysts + LLM Debate Engine</p>'
        '</div></footer>'
        '</body></html>'
    )

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return html_path


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python stock_html_report.py <analysis_result.json> [output_dir]")
        sys.exit(1)
    json_path  = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(json_path)
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    html_path = generate_html_report(data, output_dir)
    print(f"HTML report: {html_path}")
