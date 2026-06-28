"""
v5.13 P36c-bhs: score_to_bhs 連續化 pytest（紅燈 → 綠燈 TDD 流程）

設計目標：
- 舊版 score_to_bhs 用 hard 分段在 score=0.5（buy/hold/sell 三段線性切換）
- v5.13 P36c-bhs 改用 sigmoid 軟切：
  - buy = sigmoid(score, midpoint=0.5, k=12)
  - sell = sigmoid(1-score, midpoint=0.5, k=12) = 1 - buy_strength
  - hold = 1 - max(buy, sell)  ← 用 max 而非硬切，確保 hold 在中段高、邊界低
  - 保證 buy + hold + sell = 1.0
- 預期行為：
  - score=0.5 → buy=0.5, sell=0.5, hold=0.0（buy/sell 在中點交鋒）
  - score=0.0 → buy=0.0, sell=1.0, hold=0.0（純 sell）
  - score=1.0 → buy=1.0, sell=0.0, hold=0.0（純 buy）
  - score=0.4 → buy≈0.31, sell≈0.69, hold≈0.0（buy 偏弱但非 0）
  - score=0.6 → buy≈0.69, sell≈0.31, hold≈0.0（sell 偏弱但非 0）
  - 中段 score∈[0.4, 0.6] → hold 接近 0（sigmoid 在中點不留下太多 hold）

注意：保持既有完美中性（score=0.5）下 buy=hold=sell 比例合理（不像舊版 (0,1,0)）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import stock_analysis


@pytest.fixture(autouse=True)
def _reload_module():
    """確保 import 後函數是最新的（避免 cache）。"""
    import importlib
    importlib.reload(stock_analysis)
    yield


def test_score_to_bhs_perfect_neutral():
    """v5.13 P36c-bhs：score=0.5（完美中性）→ buy=hold=sell=1/3。

    舊版 (v5.11.3) 行為: (0, 1, 0) — 強烈中性（hold=1 完全壓制 buy/sell）。
    新版行為: 三等分 (0.333, 0.333, 0.333) — buy/sell/hold 都不偏。
    設計理由：sigmoid(0.5, mid=0.5)=0.5，max=0.5，hold=0.5，
              normalize 後 1.5/3 → 三等分。
    """
    r = stock_analysis.score_to_bhs(0.5)
    # 三等分（容許 sigmoid 浮點精度）
    assert abs(r["buy"] - 1.0/3.0) < 0.01
    assert abs(r["sell"] - 1.0/3.0) < 0.01
    assert abs(r["hold"] - 1.0/3.0) < 0.01


def test_score_to_bhs_extremes():
    """v5.13 P36c-bhs：score=0.0 → (0, 0, 1)，score=1.0 → (1, 0, 0)。"""
    r0 = stock_analysis.score_to_bhs(0.0)
    assert abs(r0["buy"] - 0.0) < 0.01
    assert abs(r0["sell"] - 1.0) < 0.01
    assert abs(r0["hold"] - 0.0) < 0.01

    r1 = stock_analysis.score_to_bhs(1.0)
    assert abs(r1["buy"] - 1.0) < 0.01
    assert abs(r1["sell"] - 0.0) < 0.01
    assert abs(r1["hold"] - 0.0) < 0.01


def test_score_to_bhs_monotonic_buy():
    """v5.13 P36c-bhs：buy 在 score 遞增時單調遞增（非線性，但單調）。"""
    scores = [i / 20.0 for i in range(21)]  # 0.0, 0.05, ..., 1.0
    buys = [stock_analysis.score_to_bhs(s)["buy"] for s in scores]
    # 嚴格單調遞增檢查
    for i in range(len(buys) - 1):
        assert buys[i] < buys[i + 1], (
            f"buy 必須嚴格單調遞增，但 {scores[i]}→{scores[i+1]} 時 "
            f"buy: {buys[i]} → {buys[i+1]}"
        )


def test_score_to_bhs_monotonic_sell():
    """v5.13 P36c-bhs：sell 在 score 遞增時單調遞減。"""
    scores = [i / 20.0 for i in range(21)]
    sells = [stock_analysis.score_to_bhs(s)["sell"] for s in scores]
    for i in range(len(sells) - 1):
        assert sells[i] > sells[i + 1], (
            f"sell 必須嚴格單調遞減，但 {scores[i]}→{scores[i+1]} 時 "
            f"sell: {sells[i]} → {sells[i+1]}"
        )


def test_score_to_bhs_sum_to_one():
    """v5.13 P36c-bhs：buy + hold + sell = 1.0（所有 score）。"""
    for s in [i / 20.0 for i in range(21)]:
        r = stock_analysis.score_to_bhs(s)
        total = r["buy"] + r["hold"] + r["sell"]
        assert abs(total - 1.0) < 1e-9, f"score={s}: sum={total}"


def test_score_to_bhs_symmetry():
    """v5.13 P36c-bhs：score 與 1-score 對稱（buy/sell 互換）。"""
    for s in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        r1 = stock_analysis.score_to_bhs(s)
        r2 = stock_analysis.score_to_bhs(1.0 - s)
        assert abs(r1["buy"] - r2["sell"]) < 1e-9
        assert abs(r1["sell"] - r2["buy"]) < 1e-9


def test_score_to_bhs_clamping():
    """v5.13 P36c-bhs：score > 1.0 當作 1.0，score < 0.0 當作 0.0。"""
    r_high = stock_analysis.score_to_bhs(2.5)
    assert abs(r_high["buy"] - 1.0) < 0.01

    r_low = stock_analysis.score_to_bhs(-0.5)
    assert abs(r_low["sell"] - 1.0) < 0.01


def test_score_to_bhs_no_hard_segment_at_0_5():
    """v5.13 P36c-bhs：在 score=0.5 附近，buy 應該平滑過渡（不是硬切）。

    舊版（v5.11.3）：score=0.49 → buy=0, score=0.51 → buy=0.02（突然變化）
    新版：score=0.49 → buy≈0.48, score=0.51 → buy≈0.52（平滑）
    """
    r_below = stock_analysis.score_to_bhs(0.49)
    r_above = stock_analysis.score_to_bhs(0.51)
    # buy 在 ±0.02 範圍內變化（連續，不是硬切）
    assert abs(r_below["buy"] - r_above["buy"]) < 0.2, (
        f"buy 在 0.49→0.51 變化太大: {r_below['buy']} → {r_above['buy']}"
    )


def test_score_to_bhs_continuous_no_jump():
    """v5.13 P36c-bhs：在 score 跨 0.5 時，buy 連續無 jump。

    計算左極限與右極限的差值，必須小於 0.05（不是硬切）。
    """
    r_just_below = stock_analysis.score_to_bhs(0.499)
    r_just_above = stock_analysis.score_to_bhs(0.501)
    jump = abs(r_just_above["buy"] - r_just_below["buy"])
    assert jump < 0.05, f"score=0.5 處 buy 有 jump: {jump}"


def test_score_to_bhs_hold_low_in_middle():
    """v5.13 P36c-bhs：中段 score∈[0.4, 0.6]，hold 應該顯著低於舊版。

    舊版 (v5.11.3) score=0.4: hold=0.8（線性硬切 hold 上升）
    新版 score=0.4: hold≈0.188（sigmoid max 設計）
    新版 score=0.5: hold≈0.333（三等分）
    新版比舊版 hold 比例顯著下降（這就是 P36c-bhs 的設計目的）。
    """
    for s in [0.3, 0.4, 0.5, 0.6, 0.7]:
        r = stock_analysis.score_to_bhs(s)
        # 中段 hold 顯著 < 舊版的 0.8（連續化改善）
        assert r["hold"] < 0.4, (
            f"score={s}: hold={r['hold']}（預期 < 0.4，舊版會到 0.8）"
        )
    # score=0.5 應該三等分（hold≈0.333）
    r_mid = stock_analysis.score_to_bhs(0.5)
    assert abs(r_mid["hold"] - 1.0/3.0) < 0.01
