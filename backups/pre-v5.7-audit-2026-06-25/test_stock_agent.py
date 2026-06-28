"""
Stock_Team_Agent 單元測試套件
================================
覆蓋核心模組：
- 錯誤處理框架 (errors.py)
- 情緒分析 (sentiment)
- 技術指標 (technical_indicators)
- 共識引擎 (consensus_engine)
- LLM辯論引擎 (llm_debate_engine)
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.errors import (
    ErrorCode, StockAgentBaseException, DataFetchError, DataParseError,
    APIError, APITimeoutError, APIRateLimitError, AnalysisError,
    ConsensusError, DebateEngineError, ErrorLogger, get_error_logger,
    handle_errors, error_code_to_exception, ErrorRecoveryStrategy,
    critical_error
)


# ============================================================
# 錯誤框架測試
# ============================================================
class TestErrorCodes(unittest.TestCase):
    """錯誤碼枚舉測試"""
    
    def test_error_code_values(self):
        """測試錯誤碼枚舉值正確"""
        self.assertEqual(ErrorCode.DATA_FETCH_FAILED, 1001)
        self.assertEqual(ErrorCode.API_TIMEOUT, 2003)
        self.assertEqual(ErrorCode.CONSENSUS_FAILED, 3003)
    
    def test_error_code_names(self):
        """測試錯誤碼名稱正確"""
        self.assertEqual(ErrorCode(1001).name, "DATA_FETCH_FAILED")
        self.assertEqual(ErrorCode(2003).name, "API_TIMEOUT")


class TestCustomExceptions(unittest.TestCase):
    """自定義異常測試"""
    
    def test_base_exception_str(self):
        """測試基礎異常字串表示"""
        exc = StockAgentBaseException("測試錯誤", code=ErrorCode.DATA_FETCH_FAILED)
        self.assertIn("測試錯誤", str(exc))
        self.assertIn("DATA_FETCH_FAILED", str(exc))
    
    def test_base_exception_to_dict(self):
        """測試異常轉字典"""
        exc = StockAgentBaseException("測試", code=ErrorCode.API_TIMEOUT)
        d = exc.to_dict()
        self.assertEqual(d["type"], "StockAgentBaseException")
        self.assertEqual(d["code"], "API_TIMEOUT")
        self.assertEqual(d["code_value"], 2003)
    
    def test_data_fetch_error(self):
        """測試數據獲取異常"""
        exc = DataFetchError("無法獲取數據", source="yfinance", symbol="1810.HK")
        self.assertEqual(exc.code, ErrorCode.DATA_FETCH_FAILED)
        self.assertEqual(exc.details["source"], "yfinance")
        self.assertEqual(exc.details["symbol"], "1810.HK")
    
    def test_data_fetch_error_with_cause(self):
        """測試帶原因鏈的異常"""
        cause = ConnectionError("網絡連接失敗")
        exc = DataFetchError("無法獲取", cause=cause)
        self.assertEqual(exc.cause, cause)
        self.assertIn("ConnectionError", str(exc))
    
    def test_api_timeout_error(self):
        """測試API超時異常"""
        exc = APITimeoutError("請求超時", endpoint="/v1/chat", timeout=30)
        self.assertEqual(exc.code, ErrorCode.API_TIMEOUT)
        self.assertEqual(exc.details["timeout"], 30)
    
    def test_api_rate_limit_error(self):
        """測試API速率限制異常"""
        exc = APIRateLimitError("超出限速", endpoint="/v1/chat", retry_after=60)
        self.assertEqual(exc.code, ErrorCode.API_RATE_LIMIT)
        self.assertEqual(exc.details["retry_after"], 60)
        self.assertEqual(exc.details.get("status_code"), 429)
    
    def test_analysis_error(self):
        """測試分析錯誤"""
        exc = AnalysisError("指標計算失敗", analyst="technical", indicator="RSI")
        self.assertEqual(exc.code, ErrorCode.ANALYSIS_RUNTIME_ERROR)
        self.assertEqual(exc.details["analyst"], "technical")
        self.assertEqual(exc.details["indicator"], "RSI")
    
    def test_consensus_error(self):
        """測試共識錯誤"""
        exc = ConsensusError("無法達成共識", participants=5)
        self.assertEqual(exc.code, ErrorCode.CONSENSUS_FAILED)
        self.assertEqual(exc.details["participants"], 5)
    
    def test_debate_engine_error(self):
        """測試辯論引擎錯誤"""
        exc = DebateEngineError("辯論崩潰", round_num=3, role="technical")
        self.assertEqual(exc.code, ErrorCode.DEBATE_ENGINE_ERROR)
        self.assertEqual(exc.details["round"], 3)
        self.assertEqual(exc.details["role"], "technical")


class TestErrorLogger(unittest.TestCase):
    """錯誤日誌測試"""
    
    def test_get_error_logger_singleton(self):
        """測試錯誤日誌單例"""
        logger1 = get_error_logger()
        logger2 = get_error_logger()
        self.assertIs(logger1, logger2)
    
    def test_error_logger_has_logger(self):
        """測試錯誤日誌包含logger屬性"""
        logger = get_error_logger()
        self.assertTrue(hasattr(logger, 'logger'))
        self.assertTrue(hasattr(logger, 'error'))
        self.assertTrue(hasattr(logger, 'warning'))
        self.assertTrue(hasattr(logger, 'info'))


class TestErrorCodeToException(unittest.TestCase):
    """錯誤碼到異常轉換測試"""
    
    def test_data_fetch_mapping(self):
        """測試數據獲取錯誤映射"""
        exc = error_code_to_exception(ErrorCode.DATA_FETCH_FAILED, "測試")
        self.assertIsInstance(exc, DataFetchError)
        self.assertEqual(exc.code, ErrorCode.DATA_FETCH_FAILED)
    
    def test_api_timeout_mapping(self):
        """測試API超時錯誤映射"""
        exc = error_code_to_exception(ErrorCode.API_TIMEOUT, "超時")
        self.assertIsInstance(exc, APITimeoutError)
    
    def test_consensus_mapping(self):
        """測試共識錯誤映射"""
        exc = error_code_to_exception(ErrorCode.CONSENSUS_FAILED, "共識失敗")
        self.assertIsInstance(exc, ConsensusError)


class TestErrorRecoveryStrategy(unittest.TestCase):
    """錯誤恢復策略測試"""
    
    def test_fallback_for_yfinance(self):
        """測試yfinance fallback"""
        fallback = ErrorRecoveryStrategy.get_fallback_for_data_source("yfinance")
        self.assertIsInstance(fallback, dict)
        self.assertIn("price", fallback)
    
    def test_fallback_for_rss(self):
        """測試RSS fallback"""
        fallback = ErrorRecoveryStrategy.get_fallback_for_data_source("rss_feed")
        self.assertEqual(fallback, [])
    
    def test_should_retry(self):
        """測試重試判斷"""
        self.assertTrue(ErrorRecoveryStrategy.should_retry(ErrorCode.API_RATE_LIMIT))
        self.assertTrue(ErrorRecoveryStrategy.should_retry(ErrorCode.API_TIMEOUT))
        self.assertFalse(ErrorRecoveryStrategy.should_retry(ErrorCode.API_AUTH_FAILED))
    
    def test_retry_delay_exponential_backoff(self):
        """測試指數退避"""
        delay1 = ErrorRecoveryStrategy.get_retry_delay(ErrorCode.API_RATE_LIMIT, 0)
        delay2 = ErrorRecoveryStrategy.get_retry_delay(ErrorCode.API_RATE_LIMIT, 1)
        delay3 = ErrorRecoveryStrategy.get_retry_delay(ErrorCode.API_RATE_LIMIT, 10)
        
        self.assertEqual(delay1, 5.0)
        self.assertEqual(delay2, 10.0)
        self.assertEqual(delay3, 60.0)  # 最多60秒


class TestHandleErrorsDecorator(unittest.TestCase):
    """錯誤處理裝飾器測試"""
    
    def test_decorator_returns_default_on_error(self):
        """測試裝飾器在錯誤時返回默認值"""
        @handle_errors(ErrorCode.DATA_FETCH_FAILED, default_return="FALLBACK")
        def failing_function():
            raise DataFetchError("測試失敗")
        
        result = failing_function()
        self.assertEqual(result, "FALLBACK")
    
    def test_decorator_with_retries(self):
        """測試帶重試的裝飾器"""
        call_count = [0]
        
        @handle_errors(ErrorCode.API_TIMEOUT, default_return="FALLBACK", max_retries=2, retry_delay=0.01)
        def sometimes_failing():
            call_count[0] += 1
            if call_count[0] < 3:
                raise APITimeoutError("超時")
            return "SUCCESS"
        
        result = sometimes_failing()
        self.assertEqual(result, "SUCCESS")
        self.assertEqual(call_count[0], 3)


class TestCriticalError(unittest.TestCase):
    """關鍵路徑裝飾器測試"""
    
    def test_critical_error_reraises(self):
        """測試關鍵路徑錯誤重拋"""
        @critical_error
        def critical_fail():
            raise DataFetchError("關鍵錯誤")
        
        with self.assertRaises(DataFetchError):
            critical_fail()
    
    def test_critical_error_wraps_unknown(self):
        """測試未知錯誤被包裝"""
        @critical_error
        def unknown_error():
            raise ValueError("未知錯誤")
        
        with self.assertRaises(StockAgentBaseException):
            unknown_error()


# ============================================================
# 共識引擎測試
# ============================================================
class TestConsensusEngine(unittest.TestCase):
    """共識引擎測試"""
    
    def test_dynamic_weights_sum_to_one(self):
        """測試 ConsensusEngine 權重結構（v5.3: DynamicWeightedConsensus 不存在，改測試真實引擎）"""
        try:
            from train.consensus_engine import ConsensusEngine
            engine = ConsensusEngine()
            # 驗證 analyst_weights 矩陣結構
            assert len(engine.analyst_weights) == 7  # 7 個分析師
            # 每分析師有 7 種 task_type 權重（full/technical/fundamental/risk/sentiment/news/macro）
            sample_analyst = list(engine.analyst_weights.keys())[0]
            assert len(engine.analyst_weights[sample_analyst]) >= 7
        except ImportError:
            self.skipTest("ConsensusEngine 模組不存在")

    def test_consensus_signal_generation(self):
        """測試共識信號生成（v5.3: 用真實 integrate() 方法）"""
        try:
            from train.consensus_engine import ConsensusEngine
            engine = ConsensusEngine()
            analyst_results = {
                "market":      {"score": 0.7, "signal": "buy",   "buy_score": 0.6, "hold_score": 0.3, "sell_score": 0.1, "confidence": 0.7},
                "technical":   {"score": 0.65,"signal": "buy",   "buy_score": 0.7, "hold_score": 0.2, "sell_score": 0.1, "confidence": 0.65},
                "fundamental": {"score": 0.4, "signal": "sell",  "buy_score": 0.1, "hold_score": 0.4, "sell_score": 0.5, "confidence": 0.4},
                "risk":        {"score": 0.5, "signal": "hold",  "buy_score": 0.3, "hold_score": 0.4, "sell_score": 0.3, "confidence": 0.5},
            }
            result = engine.integrate(analyst_results, "full", "TEST.HK")
            consensus = result["consensus"]
            # 買 + 持 + 賣 = 100%（百分比輸出）
            total = consensus["buy"] + consensus["hold"] + consensus["sell"]
            self.assertAlmostEqual(total, 100.0, places=1)
            # overall = (raw_buy - raw_sell) * 100，其中 raw_buy/100 = 百分比
            raw_buy = consensus["buy"] / 100
            raw_sell = consensus["sell"] / 100
            expected_overall = round((raw_buy - raw_sell) * 100, 2)
            self.assertAlmostEqual(consensus["overall"], expected_overall, places=1)
        except ImportError:
            self.skipTest("ConsensusEngine 模組不存在")


# ============================================================
# v5.4: score_to_bhs + score_to_5tier pure function tests
# ============================================================
class TestScoreMappingFunctions(unittest.TestCase):
    """v5.4: 純函數 unit test（score_to_bhs 修正 + score_to_5tier 邊界）"""

    def setUp(self):
        # 將 scripts/ 加入 path 以便 import stock_analysis
        import sys
        from pathlib import Path
        _scripts = Path(__file__).parent.parent.resolve()
        if str(_scripts) not in sys.path:
            sys.path.insert(0, str(_scripts))
        from stock_analysis import score_to_bhs, score_to_5tier
        self.score_to_bhs = score_to_bhs
        self.score_to_5tier = score_to_5tier

    def test_score_to_bhs_perfect_neutral(self):
        """score=0.5 必須完美中性 (0, 1, 0)"""
        r = self.score_to_bhs(0.5)
        self.assertAlmostEqual(r["buy"], 0.0, places=6)
        self.assertAlmostEqual(r["hold"], 1.0, places=6)
        self.assertAlmostEqual(r["sell"], 0.0, places=6)

    def test_score_to_bhs_extremes(self):
        """score=0.0 → (0,0,1)；score=1.0 → (1,0,0)"""
        r0 = self.score_to_bhs(0.0)
        self.assertAlmostEqual(r0["buy"], 0.0, places=6)
        self.assertAlmostEqual(r0["hold"], 0.0, places=6)
        self.assertAlmostEqual(r0["sell"], 1.0, places=6)
        r1 = self.score_to_bhs(1.0)
        self.assertAlmostEqual(r1["buy"], 1.0, places=6)
        self.assertAlmostEqual(r1["hold"], 0.0, places=6)
        self.assertAlmostEqual(r1["sell"], 0.0, places=6)

    def test_score_to_bhs_symmetry(self):
        """對稱性：score 與 1-score 應該是 buy↔sell 鏡像，hold 相同"""
        for s in [0.1, 0.25, 0.4, 0.6, 0.75, 0.9]:
            r1 = self.score_to_bhs(s)
            r2 = self.score_to_bhs(1.0 - s)
            self.assertAlmostEqual(r1["buy"], r2["sell"], places=6,
                msg=f"buy 鏡像失敗 score={s}")
            self.assertAlmostEqual(r1["sell"], r2["buy"], places=6,
                msg=f"sell 鏡像失敗 score={s}")
            self.assertAlmostEqual(r1["hold"], r2["hold"], places=6,
                msg=f"hold 對稱失敗 score={s}")

    def test_score_to_bhs_sum_to_one(self):
        """任何 score ∈ [0, 1] 都保證 buy+hold+sell=1.0"""
        for s in [0.0, 0.1, 0.25, 0.4, 0.5, 0.6, 0.75, 0.9, 1.0]:
            r = self.score_to_bhs(s)
            total = r["buy"] + r["hold"] + r["sell"]
            self.assertAlmostEqual(total, 1.0, places=6, msg=f"sum 失敗 score={s}")

    def test_score_to_bhs_monotonic(self):
        """buy 隨 score 單調遞增；sell 隨 score 單調遞減"""
        prev_buy = -1
        prev_sell = 2
        for s in [0.0, 0.1, 0.25, 0.4, 0.5, 0.6, 0.75, 0.9, 1.0]:
            r = self.score_to_bhs(s)
            self.assertGreaterEqual(r["buy"], prev_buy, msg=f"buy 不單調 score={s}")
            self.assertLessEqual(r["sell"], prev_sell, msg=f"sell 不單調 score={s}")
            prev_buy = r["buy"]
            prev_sell = r["sell"]

    def test_score_to_bhs_clamping(self):
        """score > 1.0 應 clamp 到 1.0；score < 0.0 應 clamp 到 0.0"""
        r_high = self.score_to_bhs(2.5)
        self.assertAlmostEqual(r_high["buy"], 1.0, places=6)
        r_low = self.score_to_bhs(-0.5)
        self.assertAlmostEqual(r_low["sell"], 1.0, places=6)

    def test_score_to_5tier_boundaries(self):
        """5-tier 邊界：±30/±60"""
        # STRONG_SELL
        self.assertEqual(self.score_to_5tier(-100), 1)
        self.assertEqual(self.score_to_5tier(-61), 1)
        # SELL
        self.assertEqual(self.score_to_5tier(-60), 2)
        self.assertEqual(self.score_to_5tier(-31), 2)
        # HOLD
        self.assertEqual(self.score_to_5tier(-30), 3)
        self.assertEqual(self.score_to_5tier(0), 3)
        self.assertEqual(self.score_to_5tier(29), 3)
        # BUY
        self.assertEqual(self.score_to_5tier(30), 4)
        self.assertEqual(self.score_to_5tier(59), 4)
        # STRONG_BUY
        self.assertEqual(self.score_to_5tier(60), 5)
        self.assertEqual(self.score_to_5tier(100), 5)

    def test_score_to_5tier_matches_consensus_engine(self):
        """5-tier 與 consensus_engine.py:295-306 完全一致（防止將來偏移）"""
        try:
            from train.consensus_engine import ConsensusEngine
            engine = ConsensusEngine()
            # 用 ConsensusEngine.integrate_pydantic 取 signal_strength
            results = {
                "market":      {"score": 0.7, "signal": "buy", "buy_score": 0.6, "hold_score": 0.3, "sell_score": 0.1, "confidence": 0.7},
                "technical":   {"score": 0.65,"signal": "buy", "buy_score": 0.7, "hold_score": 0.2, "sell_score": 0.1, "confidence": 0.65},
                "fundamental": {"score": 0.4, "signal": "sell","buy_score": 0.1, "hold_score": 0.4, "sell_score": 0.5, "confidence": 0.4},
                "risk":        {"score": 0.5, "signal": "hold","buy_score": 0.3, "hold_score": 0.4, "sell_score": 0.3, "confidence": 0.5},
            }
            cr = engine.integrate_pydantic(results, "full", "TEST.HK")
            our = self.score_to_5tier(cr.overall_score)
            self.assertEqual(our, cr.signal_strength,
                f"5-tier 不一致：score_to_5tier={our} vs ConsensusEngine={cr.signal_strength}")
        except ImportError:
            self.skipTest("ConsensusEngine 不可用")


class TestMarketScoreMultifactor(unittest.TestCase):
    """v5.5: market_score_multifactor 多因子評分測試"""

    def setUp(self):
        import sys
        from pathlib import Path
        _scripts = Path(__file__).parent.parent.resolve()
        if str(_scripts) not in sys.path:
            sys.path.insert(0, str(_scripts))
        from stock_analysis import market_score_multifactor
        self.fn = market_score_multifactor

    def test_deep_drop_buy_zone(self):
        """深度下跌應該給 buy 信號（>0.6）"""
        s = self.fn(ytd_return=-40, pos_52wk=10, from_high_pct=-50, beta=0.9)
        self.assertGreater(s, 0.6, f"深度下跌應偏買，但 score={s:.3f}")

    def test_mild_uptrend_neutral(self):
        """溫和上升趨勢 — 應該接近中性或微偏 sell（過熱）"""
        s = self.fn(ytd_return=10, pos_52wk=60, from_high_pct=5, beta=1.0)
        self.assertGreater(s, 0.3, f"上漲趨勢不應極端 sell，score={s:.3f}")
        self.assertLess(s, 0.6, f"上漲趨勢不應 buy，score={s:.3f}")

    def test_high_beta_penalty(self):
        """高 Beta 應該被微扣"""
        s_low = self.fn(ytd_return=-30, pos_52wk=20, from_high_pct=-35, beta=1.0)
        s_high = self.fn(ytd_return=-30, pos_52wk=20, from_high_pct=-35, beta=2.0)
        self.assertGreater(s_low, s_high,
            f"Beta=1.0 應 > Beta=2.0，但 {s_low:.3f} vs {s_high:.3f}")
        self.assertLess(s_high - s_low, 0.1,
            f"Beta 扣分應小幅度（<0.1），但 delta={s_low - s_high:.3f}")

    def test_output_range(self):
        """任何輸入都應該 clamp 到 [0, 1]"""
        for ytd in [-100, -50, 0, 50, 100]:
            for pos in [0, 50, 100]:
                for dd in [-100, 0, 100]:
                    for b in [0.5, 1.5, 3.0]:
                        s = self.fn(ytd, pos, dd, b)
                        self.assertGreaterEqual(s, 0.0)
                        self.assertLessEqual(s, 1.0)

    def test_v53_3value_replaced(self):
        """v5.3 的 3 值啟發式應該被取代（多樣性更高）"""
        s1 = self.fn(ytd_return=-15, pos_52wk=30, from_high_pct=-15, beta=1.0)
        s2 = self.fn(ytd_return=-25, pos_52wk=20, from_high_pct=-25, beta=1.0)
        s3 = self.fn(ytd_return=-35, pos_52wk=10, from_high_pct=-35, beta=1.0)
        self.assertLess(s1, s2, f"s1={s1:.3f} 應 < s2={s2:.3f}")
        self.assertLess(s2, s3, f"s2={s2:.3f} 應 < s3={s3:.3f}")
        self.assertGreater(abs(s1 - s2), 0.01, "v5.5 應比 v5.3 3 值有更多分辨力")


class TestTechScoreMultifactor(unittest.TestCase):
    """v5.6: tech_score_multifactor 技術分析多因子"""

    def setUp(self):
        import sys
        from pathlib import Path
        _scripts = Path(__file__).parent.parent.resolve()
        if str(_scripts) not in sys.path:
            sys.path.insert(0, str(_scripts))
        from stock_analysis import tech_score_multifactor
        self.fn = tech_score_multifactor

    def test_strong_oversold_buy(self):
        """RSI<30 + 配合其他負向因子 → 應中性偏 buy（不會極端 sell）"""
        # 設計：單 RSI 強超賣不足以 buy（其他因子需配合），但也不應 sell
        s = self.fn(rsi=25, macd_val=-1.5, price=100, ma50=110, momentum_20d=-3)
        # 對比 v5.3: 這條件 (price<ma50, macd<0) → 0.35 (sell)
        # v5.6 應 > 0.35
        self.assertGreater(s, 0.35, f"RSI=25 強超賣不應 sell，got {s:.3f}")

    def test_strong_overbought_sell(self):
        """RSI>70 強超買 + 其他中性 → 應 sell（v5.6 比 v5.3 更 sell）"""
        # 用全中性其他因子（macd=0, price=ma50, mom=0）隔離 RSI 效果
        s = self.fn(rsi=80, macd_val=0, price=100, ma50=100, momentum_20d=0)
        # 對比 v5.3: 這條件 → 0.55 (buy) — v5.3 沒有 RSI 因子
        # v5.6 RSI=80 應 < 0.5（單 RSI 強超買）
        self.assertLess(s, 0.5, f"RSI=80 單獨應 sell，got {s:.3f}")

    def test_all_aligned_buy(self):
        """所有因子都正向 → 強 buy"""
        s = self.fn(rsi=20, macd_val=2.5, price=130, ma50=100, momentum_20d=12)
        self.assertGreater(s, 0.7, f"全正向應 buy，got {s:.3f}")

    def test_all_aligned_sell(self):
        """所有因子都負向 → 強 sell"""
        s = self.fn(rsi=85, macd_val=-2.5, price=70, ma50=100, momentum_20d=-12)
        self.assertLess(s, 0.3, f"全負向應 sell，got {s:.3f}")

    def test_rsi_neutral(self):
        """RSI=50 應中性"""
        s = self.fn(rsi=50, macd_val=0, price=100, ma50=100, momentum_20d=0)
        self.assertGreater(s, 0.3)
        self.assertLess(s, 0.7)

    def test_data_missing(self):
        """ma50=0 數據不足 → 中性"""
        s = self.fn(rsi=50, macd_val=0, price=100, ma50=0, momentum_20d=0)
        self.assertGreater(s, 0.2)
        self.assertLess(s, 0.8)

    def test_output_range(self):
        for rsi in [10, 30, 50, 70, 90]:
            for macd in [-5, 0, 5]:
                for mom in [-15, 0, 15]:
                    s = self.fn(rsi, macd, 100, 100, mom)
                    self.assertGreaterEqual(s, 0.0)
                    self.assertLessEqual(s, 1.0)

    def test_v53_3value_replaced(self):
        """v5.3 的 0.35/0.55/0.45 啟發式被取代"""
        # v5.3: 弱趨勢 (price<ma50, macd<0) → 0.35; 中性 → 0.45; 強 → 0.55
        s1 = self.fn(rsi=40, macd_val=-0.5, price=95, ma50=100, momentum_20d=-2)  # 中性偏弱
        s2 = self.fn(rsi=45, macd_val=0.5, price=102, ma50=100, momentum_20d=3)   # 中性偏強
        s3 = self.fn(rsi=35, macd_val=1.5, price=108, ma50=100, momentum_20d=8)   # 強勢
        self.assertLess(s1, s3, "中性偏弱 < 強勢")
        # 對比 v5.3: s1=0.45, s2=0.55, s3=0.55（後兩者相同 — 多樣性差）
        self.assertGreater(abs(s2 - s3), 0.01, "v5.6 應比 v5.3 3 值有更多分辨力")


class TestFundScoreMultifactor(unittest.TestCase):
    """v5.6: fund_score_multifactor 基本面多因子"""

    def setUp(self):
        import sys
        from pathlib import Path
        _scripts = Path(__file__).parent.parent.resolve()
        if str(_scripts) not in sys.path:
            sys.path.insert(0, str(_scripts))
        from stock_analysis import fund_score_multifactor
        self.fn = fund_score_multifactor

    def test_strong_undervalued(self):
        """低 P/E + 高 ROE + 低 PEG + 高增長 → buy"""
        s = self.fn(pe=10, roe=0.20, peg_val=0.5, revenue_growth=0.15)
        self.assertGreater(s, 0.7, f"低估優質成長應偏買，got {s:.3f}")

    def test_expensive_no_growth(self):
        """高 P/E + 低 ROE → sell"""
        s = self.fn(pe=40, roe=0.05, peg_val=3.0, revenue_growth=-0.1)
        self.assertLess(s, 0.4, f"高估低成長應偏 sell，got {s:.3f}")

    def test_peg_none_neutral(self):
        """peg=None → 中性"""
        s = self.fn(pe=20, roe=0.10, peg_val=None, revenue_growth=0.05)
        self.assertGreater(s, 0.3)
        self.assertLess(s, 0.7)

    def test_loss_maker_penalty(self):
        """PE<=0 虧損公司 → 0.4"""
        s = self.fn(pe=-5, roe=-0.1, peg_val=None, revenue_growth=-0.1)
        self.assertLess(s, 0.5)

    def test_output_range(self):
        for pe in [-10, 5, 15, 25, 40]:
            for roe in [-0.1, 0.05, 0.15, 0.3]:
                for peg in [0.3, 1.0, 2.5, None]:
                    for rg in [-0.2, 0, 0.1, 0.3]:
                        s = self.fn(pe, roe, peg, rg)
                        self.assertGreaterEqual(s, 0.0)
                        self.assertLessEqual(s, 1.0)


class TestRiskScoreMultifactor(unittest.TestCase):
    """v5.6: risk_score_multifactor 風險多因子（高分=低風險）"""

    def setUp(self):
        import sys
        from pathlib import Path
        _scripts = Path(__file__).parent.parent.resolve()
        if str(_scripts) not in sys.path:
            sys.path.insert(0, str(_scripts))
        from stock_analysis import risk_score_multifactor
        self.fn = risk_score_multifactor

    def test_low_risk_buy(self):
        """低波動 + 小 VaR + 淺回撤 + 高 Sharpe → buy"""
        s = self.fn(volatility=15, var_95=-1, max_dd=-10, sharpe=1.5)
        self.assertGreater(s, 0.65, f"低風險應高分，got {s:.3f}")

    def test_high_risk_sell(self):
        """高波動 + 大 VaR + 深回撤 + 負 Sharpe → sell"""
        s = self.fn(volatility=50, var_95=-6, max_dd=-55, sharpe=-1.0)
        self.assertLess(s, 0.35, f"高風險應低分，got {s:.3f}")

    def test_data_missing_neutral(self):
        """波動=None → 中性"""
        s = self.fn(volatility=None, var_95=None, max_dd=None, sharpe=None)
        self.assertGreater(s, 0.3)
        self.assertLess(s, 0.7)

    def test_output_range(self):
        for v in [10, 25, 40]:
            for var in [-3, -1, 0]:
                for dd in [-30, -10, 0]:
                    for sh in [-0.5, 0.5, 1.5]:
                        s = self.fn(v, var, dd, sh)
                        self.assertGreaterEqual(s, 0.0)
                        self.assertLessEqual(s, 1.0)

    def test_v53_3value_replaced(self):
        """v5.3 的 0.35/0.55/0.45 啟發式被取代"""
        # v5.3: 低風險 (max_dd>-20, sharpe>0) → 0.55; 中性 → 0.45; 高風險 → 0.35
        s1 = self.fn(volatility=20, var_95=-1.5, max_dd=-15, sharpe=0.8)  # 低風險
        s2 = self.fn(volatility=30, var_95=-3, max_dd=-30, sharpe=0)       # 中等
        s3 = self.fn(volatility=45, var_95=-5, max_dd=-50, sharpe=-0.8)    # 高風險
        self.assertGreater(s1, s2, "低風險 > 中等")
        self.assertGreater(s2, s3, "中等 > 高風險")


# ============================================================
# v5.4: ConsensusEngine normalize sum=1 校驗（防止 C3 邊界 bug）
# ============================================================
class TestConsensusEngineNormalize(unittest.TestCase):
    """v5.4: ConsensusEngine 計算準確度回歸測試"""

    def test_consensus_pct_sum_to_100(self):
        """buy + hold + sell 必須 sum 到 100（百分比）"""
        try:
            from train.consensus_engine import ConsensusEngine
            engine = ConsensusEngine()
            # 真實輸入：buy/hold/sell 不 sum 到 1（測 C3 邊界）
            results = {
                "market":      {"score": 0.7, "signal": "buy",   "buy_score": 0.8, "hold_score": 0.3, "sell_score": 0.1, "confidence": 0.7},
                "technical":   {"score": 0.65,"signal": "buy",   "buy_score": 0.9, "hold_score": 0.2, "sell_score": 0.1, "confidence": 0.65},
                "fundamental": {"score": 0.4, "signal": "sell",  "buy_score": 0.1, "hold_score": 0.4, "sell_score": 0.6, "confidence": 0.4},
                "risk":        {"score": 0.5, "signal": "hold",  "buy_score": 0.4, "hold_score": 0.5, "sell_score": 0.3, "confidence": 0.5},
                "sentiment":   {"score": 0.55,"signal": "buy",   "buy_score": 0.5, "hold_score": 0.3, "sell_score": 0.2, "confidence": 0.55},
                "news":        {"score": 0.5, "signal": "neutral","buy_score": 0.3, "hold_score": 0.4, "sell_score": 0.3, "confidence": 0.5},
                "macro":       {"score": 0.45,"signal": "neutral","buy_score": 0.3, "hold_score": 0.4, "sell_score": 0.3, "confidence": 0.45},
            }
            r = engine.integrate(results, "full", "TEST.HK")
            consensus = r["consensus"]
            total = consensus["buy"] + consensus["hold"] + consensus["sell"]
            self.assertAlmostEqual(total, 100.0, places=1,
                msg=f"buy/hold/sell sum 不 = 100: {total:.4f}")
        except ImportError:
            self.skipTest("ConsensusEngine 不可用")


# ============================================================
# LLM辯論引擎測試
# ============================================================
class TestLLMDebateEngine(unittest.TestCase):
    """LLM辯論引擎測試"""
    
    def test_llm_debate_engine_import(self):
        """測試LLM辯論引擎可導入"""
        try:
            from 辩论.llm_debate_engine import LLMDebateEngine
            self.assertTrue(True)
        except ImportError:
            self.skipTest("LLM辯論引擎模組不存在")
    
    def test_llm_debate_has_required_methods(self):
        """測試LLM辯論引擎有所需方法"""
        try:
            from 辩论.llm_debate_engine import LLMDebateEngine
            required = ["run_debate", "get_debate_summary", "register_analyst", "send_message"]
            for method in required:
                self.assertTrue(hasattr(LLMDebateEngine, method), f"缺少方法: {method}")
        except ImportError:
            self.skipTest("LLM辯論引擎模組不存在")


# ============================================================
# 技術指標測試
# ============================================================
class TestTechnicalIndicators(unittest.TestCase):
    """技術指標測試"""
    
    def test_rsi_calculation(self):
        """測試RSI計算"""
        try:
            import pandas as pd
            from indicators.technical_indicators import calculate_rsi
            
            data = pd.Series([44, 44.2, 43.8, 44.5, 45.0, 44.8, 45.2, 45.5, 46.0, 45.8])
            rsi = calculate_rsi(data, period=14)
            self.assertIsInstance(rsi, float)
            self.assertGreaterEqual(rsi, 0)
            self.assertLessEqual(rsi, 100)
        except ImportError:
            self.skipTest("技術指標模組不存在")
    
    def test_macd_calculation(self):
        """測試MACD計算"""
        try:
            import pandas as pd
            from indicators.technical_indicators import calculate_macd
            
            data = pd.Series([100 + i * 0.5 for i in range(50)])
            macd, signal, histogram = calculate_macd(data)
            self.assertIsInstance(macd, float)
        except ImportError:
            self.skipTest("技術指標模組不存在")


# ============================================================
# 運行所有測試
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Stock_Team_Agent 單元測試套件")
    print("=" * 60)
    unittest.main(verbosity=2)
