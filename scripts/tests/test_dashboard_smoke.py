"""Smoke test: dashboard index.html 結構驗證 (no browser, pure file inspection)."""

import re
import sys
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parent.parent.parent / "dashboard" / "index.html"


def test_html_exists():
    assert DASHBOARD.exists(), f"dashboard not found: {DASHBOARD}"
    print(f"✓ dashboard exists: {DASHBOARD}")


def test_html_loads_fixture():
    """驗證 HTML 引用 fixture 路徑。"""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert "tickers_fundamentals.json" in html, "fixture reference missing"
    print("✓ HTML references fixture JSON")


def test_html_has_11_ticker_slots_via_sort():
    """驗證 render function 會 iterate Object.keys() 排序 → 11 cards. (Static check: 沒有 hardcode count)"""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert "Object.keys(sd).sort()" in html, "ticker iteration missing"
    assert ".map(t => renderCard(t, sd[t]))" in html, "card rendering loop missing"
    print("✓ HTML iterates over fixture tickers (dynamic, no hardcode count)")


def test_html_displays_7_components():
    """驗證 7 個 component sub-scores: market, tech, fund, risk, sentiment, news, macro."""
    html = DASHBOARD.read_text(encoding="utf-8")
    for comp in ["market", "technical", "fundamental", "risk", "sentiment", "news", "macro"]:
        assert comp in html, f"component '{comp}' missing in HTML"
    print("✓ HTML displays 7 multifactor components")


def test_html_has_risk_classification():
    """驗證 HIGH-risk 標記邏輯。"""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert "HIGH_RISK_TICKERS" in html, "HIGH_RISK_TICKERS set missing"
    assert "'AAPL'" in html, "AAPL high-risk classification missing"
    assert "'GOOGL'" in html, "GOOGL high-risk classification missing"
    assert "'000333.SZ'" in html, "000333.SZ high-risk classification missing"
    assert "'000858.SZ'" in html, "000858.SZ high-risk classification missing"
    assert "'600519.SS'" in html, "600519.SS high-risk classification missing"
    print("✓ HTML classifies 5 HIGH-risk tickers per v5.26 brief")


def test_html_has_close_source_toggle():
    """驗證 close_source mock/real 切換 (Step 3 改進)."""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert "setCloseSource" in html, "close_source toggle function missing"
    assert "real" in html and "mock" in html, "real/mock labels missing"
    print("✓ HTML has close_source toggle (real/mock)")


def test_html_has_api_integration():
    """驗證 dashboard 串接 dashboard_api FastAPI endpoint."""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert "fetchCrossMarket" in html, "fetchCrossMarket helper missing"
    assert "/api/cross_market" in html, "API endpoint URL missing"
    assert "close_source=" in html, "close_source query param missing"
    assert "fetch(" in html, "fetch call missing"
    print("✓ HTML integrates with dashboard API (fetch /api/cross_market)")


def test_html_has_async_setCloseSource():
    """驗證 setCloseSource 為 async + 真實切換 (而非只切 label)。"""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert "async function setCloseSource" in html, "setCloseSource not async"
    # 真實切換應呼叫 fetchCrossMarket
    assert html.count("fetchCrossMarket(") >= 3, "setCloseSource 沒呼叫 fetchCrossMarket"
    print("✓ HTML setCloseSource async + 真實切換 API")


def test_html_has_summary_stats():
    """驗證 6 個 summary stat cards: Tickers, BUY, HOLD, SELL, HIGH-Risk, mean final_score."""
    html = DASHBOARD.read_text(encoding="utf-8")
    for stat in ["Tickers", "BUY Signals", "HOLD Signals", "SELL Signals", "HIGH-Risk", "Mean final_score"]:
        assert stat in html, f"summary stat '{stat}' missing"
    print("✓ HTML shows 6 summary stats")


def test_html_has_signal_distribution_bar():
    """驗證 BUY/HOLD/SELL 視覺化比例條。"""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert "signal-buy" in html and "signal-hold" in html and "signal-sell" in html
    assert "signal-bar" in html
    print("✓ HTML has signal distribution bar (BUY/HOLD/SELL visual)")


def test_html_dark_theme():
    """驗證 dark theme (operator dashboard 標準)."""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert "--bg: #0f1419" in html, "dark theme bg color missing"
    print("✓ HTML has dark theme styling")


def test_no_console_errors_in_static_load():
    """靜態掃描明顯的 JS 錯誤。"""
    html = DASHBOARD.read_text(encoding="utf-8")
    # 檢查常見 JS 錯誤模式
    assert "undefined.function" not in html, "undefined function call detected"
    assert "console.log" not in html or "debug" in html.lower(), "stray console.log in production"
    print("✓ no obvious JS errors in static load")


def test_html_has_dimension_toggle():
    """v5.28 P2 — 4D / 7D toggle 必須存在於 #dim-toggle container"""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert 'id="dim-toggle"' in html, "缺 4D/7D dimension toggle container"
    assert "setDimension" in html, "缺 setDimension() handler"
    assert "fetchCrossMarket7D" in html, "缺 fetchCrossMarket7D() call"
    # 4D 與 7D 按鈕
    assert ">4D<" in html, "缺 4D button"
    assert ">7D<" in html, "缺 7D button"
    print("✓ dimension toggle 4D/7D exists with handler")


def test_html_separates_src_and_dim_toggles():
    """v5.28 P2 — close_source toggle 與 dimension toggle 必須分離 (id 不同)"""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert 'id="src-toggle"' in html, "缺 src-toggle container"
    assert 'id="dim-toggle"' in html, "缺 dim-toggle container"
    # 確保 setCloseSource 只 querySelectorAll src-toggle (不會清除 dim-toggle 的 active 狀態)
    assert "setCloseSource" in html
    src_block = html[html.find("async function setCloseSource"):html.find("async function setDimension")]
    assert "'#src-toggle button'" in src_block, "setCloseSource 必須 scope 到 src-toggle"
    print("✓ src-toggle 與 dim-toggle 分離, setCloseSource scope 正確")


def test_html_renders_7d_composite_when_mode_7d():
    """v5.28 P2 — renderCard() 必須在 7D 模式顯示 composite_7d 而非 final_score"""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert "is7D" in html, "renderCard() 缺 is7D 模式判斷"
    assert "composite_7d" in html, "缺 composite_7d 引用"
    assert "render7D()" in html, "缺 render7D() function"
    assert "render4D()" in html, "缺 render4D() function (從原 render() 拆出)"
    print("✓ renderCard 支援 4D/7D 模式切換")


def test_html_7d_endpoint_url():
    """v5.28 P2 — fetchCrossMarket7D() 必須指向 /api/cross_market_7d"""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert "/api/cross_market_7d" in html, "缺 /api/cross_market_7d URL"
    print("✓ 7D endpoint URL exists")


# === v5.30 P3 — per-region toggle frontend guards ===

def test_html_has_region_toggle():
    """v5.30 P3 — #region-toggle container 必須存在 (per-region 切換 UI)"""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert 'id="region-toggle"' in html, "缺 #region-toggle container"
    print("✓ region toggle container exists")


def test_html_region_toggle_has_four_buttons():
    """v5.30 P3 — #region-toggle 必須有 4 個按鈕: Global/US/HK/CN"""
    html = DASHBOARD.read_text(encoding="utf-8")
    # 找出 region-toggle block
    start = html.find('id="region-toggle"')
    assert start != -1, "缺 #region-toggle"
    # 找下一個 </div> (同層級的 controls wrapper 結束,簡化找下一個 toggle)
    end = html.find('id="src-toggle"', start)
    block = html[start:end]
    # 4 個 region 按鈕
    for label in ["Global", "US", "HK", "CN"]:
        assert f">{label}<" in block, f"region button '{label}' missing in #region-toggle"
    print("✓ region toggle has 4 buttons (Global/US/HK/CN)")


def test_html_setregion_handler_exists():
    """v5.30 P3 — setRegion() JS handler 必須存在,需 async + querySelectorAll region-toggle"""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert "async function setRegion" in html, "缺 async setRegion() handler"
    # 必須 scope 到 region-toggle (不會影響其他 toggle)
    assert "'#region-toggle button'" in html, "setRegion 必須 scope 到 region-toggle"
    print("✓ setRegion handler exists with proper scoping")


def test_html_region_toggle_passes_query_param():
    """v5.30 P3 — fetchCrossMarket7D 必須帶 region query param"""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert "region=" in html, "缺 region= query param"
    # 確認在 7D fetch 函數內
    start = html.find("async function fetchCrossMarket7D")
    end = html.find("async function loadRegionConfig", start)
    block = html[start:end]
    assert "region=" in block, "fetchCrossMarket7D 未帶 region query param"
    assert "currentRegion" in html, "缺 currentRegion state"
    print("✓ fetchCrossMarket7D passes region query param")


def test_html_card_renders_region_badge():
    """v5.30 P3 — renderCard 必須在 7D 模式顯示 region badge 與 advice"""
    html = DASHBOARD.read_text(encoding="utf-8")
    # renderCard 內的 region badge 模板
    assert "data.region" in html, "renderCard 缺 data.region 引用"
    assert "data.advice" in html, "renderCard 缺 data.advice 引用"
    # 確認 cardData mapping 有 region/advice
    assert "region: regionVal" in html, "cardData 缺 region field"
    assert "advice: adviceVal" in html, "cardData 缺 advice field"
    print("✓ card renders region badge + advice in 7D mode")


def main():
    tests = [
        test_html_exists,
        test_html_loads_fixture,
        test_html_has_11_ticker_slots_via_sort,
        test_html_displays_7_components,
        test_html_has_risk_classification,
        test_html_has_close_source_toggle,
        test_html_has_api_integration,
        test_html_has_async_setCloseSource,
        test_html_has_summary_stats,
        test_html_has_signal_distribution_bar,
        test_html_dark_theme,
        test_no_console_errors_in_static_load,
        test_html_has_dimension_toggle,
        test_html_separates_src_and_dim_toggles,
        test_html_renders_7d_composite_when_mode_7d,
        test_html_7d_endpoint_url,
        # v5.30 P3 — per-region toggle
        test_html_has_region_toggle,
        test_html_region_toggle_has_four_buttons,
        test_html_setregion_handler_exists,
        test_html_region_toggle_passes_query_param,
        test_html_card_renders_region_badge,
    ]
    for t in tests:
        t()
    print(f"\n✅ {len(tests)}/{len(tests)} dashboard smoke tests passed")


if __name__ == "__main__":
    sys.exit(main())
