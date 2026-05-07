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
        """測試動態權重總和為1"""
        try:
            from consensus.consensus_engine import DynamicWeightedConsensus
            
            positions = {
                "technical": {"score": 0.7, "signal": "buy"},
                "fundamental": {"score": 0.6, "signal": "hold"},
                "sentiment": {"score": 0.5, "signal": "sell"},
            }
            
            consensus = DynamicWeightedConsensus()
            weights = consensus.calculate_dynamic_weights(positions)
            
            total = sum(weights.values())
            self.assertAlmostEqual(total, 1.0, places=5)
        except ImportError:
            self.skipTest("共識引擎模組不存在")
    
    def test_consensus_signal_generation(self):
        """測試共識信號生成"""
        try:
            from consensus.consensus_engine import DynamicWeightedConsensus
            
            consensus = DynamicWeightedConsensus()
            
            final_scores = {
                "technical": 0.7,
                "fundamental": 0.65,
                "sentiment": 0.4,
                "risk": 0.5,
            }
            
            signal = consensus.get_final_signal(final_scores, threshold=0.55)
            self.assertIn(signal, ["buy", "hold", "sell"])
        except ImportError:
            self.skipTest("共識引擎模組不存在")


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
