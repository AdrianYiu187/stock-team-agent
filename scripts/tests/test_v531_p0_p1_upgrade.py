"""v5.31 P0+P1 TDD guards — 鎖定 dead code 修正 + HK 真實 7D 升級 shape。

8 guards:
  1. test_app_version_is_v531 (critical fix from audit)
  2. test_weights_4d_fund_heavy_constant_extracted
  3. test_buy_sell_threshold_constants_extracted
  4. test_per_region_weights_uses_weights_4d_fund_heavy
  5. test_extended_signal_distribution_shape_lock
  6. test_full_7d_e2e_components_have_real_sentiment
  7. test_hk_proxy_to_full_upgrade_plan_documented
  8. test_no_dead_hardcoded_weight_in_region_weights
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import dashboard_api  # noqa: E402
from backtest_v511_multifactor import MULTIFACTOR_WEIGHTS  # noqa: E402


FIXTURE_PATH = (
    _REPO_ROOT / "scripts" / "tests" / "fixtures" / "tickers_fundamentals.json"
)


class TestV531P0DeadCodeFix(unittest.TestCase):
    """P0 — 死碼審計修正後的 invariants (3 critical/warning fix 鎖定)。"""

    def test_01_app_version_is_v531(self):
        """audit critical: version_drift → app.version 升級為 5.31.0"""
        self.assertEqual(
            dashboard_api.app.version,
            "5.31.0",
            f"app.version={dashboard_api.app.version} 應為 '5.31.0'",
        )

    def test_02_weights_4d_fund_heavy_constant_extracted(self):
        """audit warning: hardcoded_weight_reuse_multifactor_weights → 提取常數"""
        self.assertTrue(
            hasattr(dashboard_api, "WEIGHTS_4D_FUND_HEAVY"),
            "應有 WEIGHTS_4D_FUND_HEAVY 常數",
        )
        w = dashboard_api.WEIGHTS_4D_FUND_HEAVY
        # 4 個 fund_heavy 維度必須等於 MULTIFACTOR_WEIGHTS
        for k, v in MULTIFACTOR_WEIGHTS.items():
            self.assertEqual(w[k], v, f"WEIGHTS_4D_FUND_HEAVY[{k}]={w[k]} ≠ MULTIFACTOR_WEIGHTS[{k}]={v}")
        # 3 個 7D-only 維度必須為 0
        for k in ("sentiment", "news", "macro"):
            self.assertEqual(w[k], 0.0, f"WEIGHTS_4D_FUND_HEAVY[{k}] 應為 0 (4D only)")
        # sum = 1.0
        self.assertAlmostEqual(sum(w.values()), 1.0, places=4)

    def test_03_buy_sell_threshold_constants_extracted(self):
        """audit info: hardcoded_threshold_extract_constant → 提取 BUY/SELL_THRESHOLD"""
        self.assertTrue(hasattr(dashboard_api, "BUY_THRESHOLD"))
        self.assertTrue(hasattr(dashboard_api, "SELL_THRESHOLD"))
        self.assertEqual(dashboard_api.BUY_THRESHOLD, 0.58)
        self.assertEqual(dashboard_api.SELL_THRESHOLD, 0.45)

    def test_04_per_region_weights_uses_weights_4d_fund_heavy(self):
        """HK/CN region weights 應 reuse WEIGHTS_4D_FUND_HEAVY 而非 hardcoded"""
        for region in ("HK", "CN"):
            actual = dashboard_api.PER_REGION_WEIGHTS_7D_CLEAN[region]
            expected = dashboard_api.WEIGHTS_4D_FUND_HEAVY
            self.assertEqual(
                actual, expected,
                f"{region} region weights 應與 WEIGHTS_4D_FUND_HEAVY 完全相同 (避免硬碼 drift)",
            )


class TestV531P1UpgradeShape(unittest.TestCase):
    """P1 — proxy → full 7D upgrade shape 鎖定 (升級 script 實作前的合約)。

    v5.31 P1 目標: 對 12 個 extended_signal_distribution_per_ticker 的 ticker
    把 proxy (sentiment/news/macro 全 0.5) 升級為真實 e2e 計算的 [0,1] 分數。
    本測試鎖定升級合約 (待 scripts/upgrade_extended_to_full_7d.py 實作)。
    """

    def test_05_extended_signal_distribution_shape_lock(self):
        """12 ticker 都有 components 含 7 keys"""
        data = json.loads(FIXTURE_PATH.read_text())
        ext = data.get("extended_signal_distribution_per_ticker", {})
        self.assertEqual(
            len(ext), 12,
            f"expected 12 ticker in extended_signal_distribution_per_ticker, got {len(ext)}",
        )
        required_keys = {"tech", "fund", "market", "risk", "sentiment", "news", "macro"}
        for ticker, info in ext.items():
            comps = info.get("components", {})
            self.assertEqual(
                set(comps.keys()), required_keys,
                f"{ticker} components keys 應為 {required_keys}, got {set(comps.keys())}",
            )

    def test_06_full_7d_e2e_components_have_real_sentiment(self):
        """升級後: 7D components 不能全 0.5 (proxy) — 必須有真實變異"""
        data = json.loads(FIXTURE_PATH.read_text())
        ext = data["extended_signal_distribution_per_ticker"]

        # 統計 sentiment/news/macro 是否全 0.5 (proxy) 或有變異 (real)
        hk_proxy_count = 0
        hk_real_count = 0
        for ticker, info in ext.items():
            if ticker.endswith(".HK"):
                comps = info["components"]
                is_proxy_sent = all(
                    comps[k] == 0.5 for k in ("sentiment", "news", "macro")
                )
                if is_proxy_sent:
                    hk_proxy_count += 1
                else:
                    hk_real_count += 1

        # 升級目標: HK 6 ticker 至少 4 個要有真實變異 (不是全 0.5)
        # 當前: 全 6 個都是 proxy (sentiment/news/macro=0.5)
        # 升級後: hk_real_count >= 4
        self.assertGreaterEqual(
            hk_real_count, 4,
            f"v5.31 P1 升級目標: HK ≥ 4 ticker 有真實 sentiment/news/macro "
            f"(當前 hk_real={hk_real_count}, hk_proxy={hk_proxy_count})。",
        )

    def test_07_hk_proxy_to_full_upgrade_plan_documented(self):
        """確認 scripts/upgrade_extended_to_full_7d.py 存在 (升級計劃已記錄)"""
        upgrade_script = _REPO_ROOT / "scripts" / "upgrade_extended_to_full_7d.py"
        self.assertTrue(
            upgrade_script.exists(),
            f"v5.31 P1 升級 script 應存在: {upgrade_script}",
        )
        # 必須包含函數 `upgrade_ticker` 或 `upgrade_all_extended`
        src = upgrade_script.read_text()
        self.assertTrue(
            "def upgrade" in src,
            "upgrade_extended_to_full_7d.py 應有 upgrade_* 函數",
        )

    def test_08_no_dead_hardcoded_weight_in_region_weights(self):
        """P0 修正後: HK/CN region weights 不應有 hardcoded tech:0.20 模式"""
        for region in ("HK", "CN"):
            w = dashboard_api.PER_REGION_WEIGHTS_7D_CLEAN[region]
            # 必須與 WEIGHTS_4D_FUND_HEAVY 完全相同 (證明 reuse)
            self.assertEqual(
                w, dashboard_api.WEIGHTS_4D_FUND_HEAVY,
                f"{region} region weights 與 WEIGHTS_4D_FUND_HEAVY 不一致 — 仍有 hardcoded",
            )


if __name__ == "__main__":
    unittest.main()