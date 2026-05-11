"""
Alpha Vantage Security Utils Module
Ported from TradingAgents dataflows/utils.py

Security utilities for ticker validation to prevent path traversal attacks.
"""

import os
import re
from datetime import date, datetime, timedelta
from typing import Annotated

SavePathType = Annotated[str, "File path to save data. If None, data is not saved."]

# Tickers can contain letters, digits, dot, dash, underscore, and caret
# (for index symbols like ^GSPC). Anything else is rejected.
_TICKER_PATH_RE = re.compile(r"^[A-Za-z0-9._\-\^]+$")


def safe_ticker_component(value: str, *, max_len: int = 32) -> str:
    """Validate ticker is safe for filesystem path interpolation.

    Tickers come from user input or LLM tool calls, both of which can be
    influenced by attacker-controlled content (e.g. prompt injection).
    
    Without validation, values like "../../../etc/foo" could escape the
    cache directory when interpolated into paths.

    Args:
        value: The ticker symbol to validate
        max_len: Maximum allowed length (default: 32)
        
    Returns:
        The validated ticker value unchanged
        
    Raises:
        ValueError: If ticker is empty, too long, or contains invalid characters
        ValueError: If ticker consists solely of dots (path traversal attempt)
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"ticker must be a non-empty string, got {value!r}")
    if len(value) > max_len:
        raise ValueError(f"ticker exceeds {max_len} chars: {value!r}")
    if not _TICKER_PATH_RE.fullmatch(value):
        raise ValueError(
            f"ticker contains characters not allowed: {value!r}. "
            f"Only [A-Za-z0-9._\\-^] allowed."
        )
    # Block dots-only values (., .., etc.)
    if set(value) == {"."}:
        raise ValueError(f"ticker cannot be dots only: {value!r}")
    return value


def save_output(data, tag: str, save_path: SavePathType = None) -> None:
    """Save data to CSV file if save_path is provided.
    
    Args:
        data: Pandas DataFrame or similar to save
        tag: Label for logging
        save_path: File path, or None to skip saving
    """
    if save_path:
        data.to_csv(save_path, encoding="utf-8")
        print(f"{tag} saved to {save_path}")


def get_current_date() -> str:
    """Get current date in YYYY-MM-DD format."""
    return date.today().strftime("%Y-%m-%d")


def get_next_weekday(date_input) -> datetime:
    """Get next weekday (Monday-Friday) from given date.
    
    Args:
        date_input: Date string YYYY-MM-DD or datetime object
        
    Returns:
        datetime of next weekday
    """
    if not isinstance(date_input, datetime):
        date_input = datetime.strptime(date_input, "%Y-%m-%d")

    if date_input.weekday() >= 5:  # Saturday=5, Sunday=6
        days_to_add = 7 - date_input.weekday()
        return date_input + timedelta(days=days_to_add)
    return date_input


def decorate_all_methods(decorator):
    """Class decorator to apply a decorator to all methods of a class.
    
    Args:
        decorator: Decorator function to apply to each method
        
    Returns:
        Class decorator function
    """
    def class_decorator(cls):
        for attr_name, attr_value in cls.__dict__.items():
            if callable(attr_value):
                setattr(cls, attr_name, decorator(attr_value))
        return cls
    return class_decorator
