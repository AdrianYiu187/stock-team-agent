"""
Stock_Team_Agent 統一錯誤處理框架
===================================
- 自定義異常類層次結構
- 統一錯誤碼定義
- 結構化錯誤日誌
- 自動錯誤恢復策略
"""

import traceback
import functools
import time
import logging
from typing import Any, Callable, Optional, Dict
from datetime import datetime
from enum import IntEnum

# ============================================================
# 錯誤碼定義 (Error Codes)
# ============================================================
class ErrorCode(IntEnum):
    """錯誤碼枚舉"""
    # 數據獲取錯誤 (1000-1999)
    DATA_FETCH_FAILED = 1001
    DATA_PARSE_FAILED = 1002
    DATA_VALIDATION_FAILED = 1003
    CACHE_MISS = 1004
    
    # API 錯誤 (2000-2999)
    API_RATE_LIMIT = 2001
    API_AUTH_FAILED = 2002
    API_TIMEOUT = 2003
    API_RESPONSE_INVALID = 2004
    
    # 分析錯誤 (3000-3999)
    ANALYSIS_RUNTIME_ERROR = 3001
    INDICATOR_CALC_FAILED = 3002
    CONSENSUS_FAILED = 3003
    DEBATE_ENGINE_ERROR = 3004
    
    # 系統錯誤 (4000-4999)
    CONFIG_MISSING = 4001
    MODULE_IMPORT_FAILED = 4002
    FILE_OPERATION_FAILED = 4003


# ============================================================
# 自定義異常類層次
# ============================================================
class StockAgentBaseException(Exception):
    """所有自定義異常的基類"""
    
    def __init__(self, message: str, code: ErrorCode = None, details: Dict = None, cause: Exception = None):
        self.message = message
        self.code = code
        self.details = details or {}
        self.cause = cause
        self.timestamp = datetime.now().isoformat()
        super().__init__(self.message)
    
    def __str__(self):
        parts = [f"[{self.code.name if self.code else 'UNKNOWN'}] {self.message}"]
        if self.cause:
            parts.append(f"原因: {type(self.cause).__name__}: {str(self.cause)}")
        if self.details:
            parts.append(f"詳情: {self.details}")
        return " | ".join(parts)
    
    def to_dict(self) -> Dict:
        """轉換為字典格式，便於日誌和序列化"""
        return {
            "type": self.__class__.__name__,
            "code": self.code.name if self.code else None,
            "code_value": int(self.code) if self.code else None,
            "message": self.message,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
            "timestamp": self.timestamp
        }


class DataFetchError(StockAgentBaseException):
    """數據獲取錯誤"""
    def __init__(self, message: str, source: str = None, symbol: str = None, cause: Exception = None):
        details = {}
        if source:
            details["source"] = source
        if symbol:
            details["symbol"] = symbol
        super().__init__(
            message=message,
            code=ErrorCode.DATA_FETCH_FAILED,
            details=details,
            cause=cause
        )


class DataParseError(StockAgentBaseException):
    """數據解析錯誤"""
    def __init__(self, message: str, raw_data: str = None, cause: Exception = None):
        details = {}
        if raw_data and len(raw_data) < 500:
            details["raw_data_preview"] = raw_data[:200]
        super().__init__(
            message=message,
            code=ErrorCode.DATA_PARSE_FAILED,
            details=details,
            cause=cause
        )


class APIError(StockAgentBaseException):
    """API 調用錯誤"""
    def __init__(self, message: str, endpoint: str = None, status_code: int = None, cause: Exception = None):
        details = {}
        if endpoint:
            details["endpoint"] = endpoint
        if status_code:
            details["status_code"] = status_code
        super().__init__(
            message=message,
            code=ErrorCode.API_RESPONSE_INVALID,
            details=details,
            cause=cause
        )


class APITimeoutError(APIError):
    """API 超時錯誤"""
    def __init__(self, message: str, endpoint: str = None, timeout: int = None, cause: Exception = None):
        super().__init__(
            message=message,
            endpoint=endpoint,
            status_code=None,
            cause=cause
        )
        self.code = ErrorCode.API_TIMEOUT
        if timeout:
            self.details["timeout"] = timeout


class APIRateLimitError(APIError):
    """API 速率限制錯誤"""
    def __init__(self, message: str, endpoint: str = None, retry_after: int = None, cause: Exception = None):
        super().__init__(
            message=message,
            endpoint=endpoint,
            status_code=429,
            cause=cause
        )
        self.code = ErrorCode.API_RATE_LIMIT
        if retry_after:
            self.details["retry_after"] = retry_after


class AnalysisError(StockAgentBaseException):
    """分析過程錯誤"""
    def __init__(self, message: str, analyst: str = None, indicator: str = None, cause: Exception = None):
        details = {}
        if analyst:
            details["analyst"] = analyst
        if indicator:
            details["indicator"] = indicator
        super().__init__(
            message=message,
            code=ErrorCode.ANALYSIS_RUNTIME_ERROR,
            details=details,
            cause=cause
        )


class ConsensusError(StockAgentBaseException):
    """共識計算錯誤"""
    def __init__(self, message: str, participants: int = None, cause: Exception = None):
        details = {"participants": participants} if participants else {}
        super().__init__(
            message=message,
            code=ErrorCode.CONSENSUS_FAILED,
            details=details,
            cause=cause
        )


class DebateEngineError(StockAgentBaseException):
    """辯論引擎錯誤"""
    def __init__(self, message: str, round_num: int = None, role: str = None, cause: Exception = None):
        details = {}
        if round_num is not None:
            details["round"] = round_num
        if role:
            details["role"] = role
        super().__init__(
            message=message,
            code=ErrorCode.DEBATE_ENGINE_ERROR,
            details=details,
            cause=cause
        )


# ============================================================
# 統一錯誤日誌處理器
# ============================================================
class ErrorLogger:
    """結構化錯誤日誌"""
    
    def __init__(self, name: str = "StockAgent"):
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def error(self, exc: StockAgentBaseException, context: str = None):
        """記錄錯誤"""
        msg_parts = [f"[{exc.code.name if exc.code else 'UNKNOWN'}] {exc.message}"]
        if context:
            msg_parts.append(f"上下文: {context}")
        if exc.cause:
            msg_parts.append(f"原因: {type(exc.cause).__name__}: {str(exc.cause)}")
        if exc.details:
            msg_parts.append(f"詳情: {exc.details}")
        
        self.logger.error(" | ".join(msg_parts))
        if exc.cause and isinstance(exc.cause, Exception):
            self.logger.debug(traceback.format_exc())
    
    def warning(self, message: str, code: str = None):
        """記錄警告"""
        tag = f"[{code}] " if code else ""
        self.logger.warning(f"{tag}{message}")
    
    def info(self, message: str):
        """記錄信息"""
        self.logger.info(message)


# 全域錯誤日誌實例
_error_logger = None

def get_error_logger() -> ErrorLogger:
    """獲取全域錯誤日誌實例"""
    global _error_logger
    if _error_logger is None:
        _error_logger = ErrorLogger()
    return _error_logger


# ============================================================
# 錯誤處理裝飾器工廠
# ============================================================
def handle_errors(
    error_code: ErrorCode,
    default_return: Any = None,
    max_retries: int = 0,
    retry_delay: float = 1.0,
    log_level: str = "error"
):
    """
    統一的錯誤處理裝飾器
    
    Args:
        error_code: 錯誤碼枚舉
        default_return: 錯誤時返回的默認值
        max_retries: 最大重試次數
        retry_delay: 重試延遲（秒）
        log_level: 日誌級別 (error/warning/info)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_error_logger()
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except StockAgentBaseException as e:
                    if attempt == max_retries:
                        logger.error(e, context=f"{func.__name__}")
                        return default_return
                    time.sleep(retry_delay)
                except Exception as e:
                    if attempt == max_retries:
                        wrapped = error_code_to_exception(error_code, str(e), cause=e)
                        logger.error(wrapped, context=f"{func.__name__}")
                        raise wrapped
                    time.sleep(retry_delay)
            
            return default_return
        
        return wrapper
    return decorator


def error_code_to_exception(code: ErrorCode, message: str, **kwargs) -> StockAgentBaseException:
    """根據錯誤碼創建對應異常"""
    mapping = {
        ErrorCode.DATA_FETCH_FAILED: DataFetchError,
        ErrorCode.DATA_PARSE_FAILED: DataParseError,
        ErrorCode.API_TIMEOUT: APITimeoutError,
        ErrorCode.API_RATE_LIMIT: APIRateLimitError,
        ErrorCode.API_RESPONSE_INVALID: APIError,
        ErrorCode.ANALYSIS_RUNTIME_ERROR: AnalysisError,
        ErrorCode.CONSENSUS_FAILED: ConsensusError,
        ErrorCode.DEBATE_ENGINE_ERROR: DebateEngineError,
    }
    exc_class = mapping.get(code, StockAgentBaseException)
    return exc_class(message=message, **kwargs)


# ============================================================
# 錯誤恢復策略
# ============================================================
class ErrorRecoveryStrategy:
    """錯誤自動恢復策略"""
    
    @staticmethod
    def get_fallback_for_data_source(source: str) -> Any:
        """根據數據源獲取fallback值"""
        fallback_map = {
            "yfinance": {"price": 0.0, "change_pct": 0.0, "volume": 0},
            "rss_feed": [],
            "news_provider": [],
            "technical_indicators": {"rsi": 50.0, "macd": 0.0, "ma20": 0.0, "ma50": 0.0},
        }
        return fallback_map.get(source, None)
    
    @staticmethod
    def should_retry(code: ErrorCode) -> bool:
        """判斷是否應該重試"""
        retryable_codes = {
            ErrorCode.DATA_FETCH_FAILED,
            ErrorCode.API_TIMEOUT,
            ErrorCode.API_RATE_LIMIT,
            ErrorCode.CACHE_MISS,
        }
        return code in retryable_codes
    
    @staticmethod
    def get_retry_delay(code: ErrorCode, attempt: int) -> float:
        """獲取重試延遲（指數退避）"""
        base_delays = {
            ErrorCode.API_RATE_LIMIT: 5.0,
            ErrorCode.API_TIMEOUT: 2.0,
            ErrorCode.DATA_FETCH_FAILED: 1.0,
        }
        base = base_delays.get(code, 1.0)
        return min(base * (2 ** attempt), 60.0)  # 最多60秒


# ============================================================
# 快速失敗裝飾器（用於關鍵路徑）
# ============================================================
def critical_error(func: Callable) -> Callable:
    """關鍵路徑裝飾器 - 遇到錯誤直接重拋"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except StockAgentBaseException:
            raise
        except Exception as e:
            logger = get_error_logger()
            wrapped = StockAgentBaseException(
                message=f"關鍵路徑錯誤: {func.__name__}",
                code=ErrorCode.ANALYSIS_RUNTIME_ERROR,
                cause=e
            )
            logger.error(wrapped, context=func.__name__)
            raise wrapped
    return wrapper
