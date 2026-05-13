"""
JSON-based checkpointing for stock_analysis.py

Provides atomic save/load of analysis progress to allow resumption
after interruption or crash. Uses JSON files in /tmp/ directory.
"""

import json
import os
import tempfile
from datetime import datetime
from typing import Optional, Dict, Any


CHECKPOINT_DIR = "/tmp"
CHECKPOINT_PREFIX = "stock_analysis_checkpoint_"


def _get_checkpoint_path(ticker: str) -> str:
    """Get the checkpoint file path for a ticker."""
    return os.path.join(CHECKPOINT_DIR, CHECKPOINT_PREFIX + ticker.upper() + ".json")


def save_checkpoint(ticker: str, phase: str, data: dict) -> bool:
    """
    Save a checkpoint atomically using temp file + rename pattern.
    
    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        phase: Current phase name (e.g., "data", "news", "debate", "report")
        data: Dictionary containing phase-specific data to persist
    
    Returns:
        True if save succeeded, False otherwise
    """
    checkpoint_path = _get_checkpoint_path(ticker)
    
    # Load existing checkpoint to preserve completed_phases
    existing = load_checkpoint(ticker)
    if existing:
        completed = existing.get("completed_phases", [])
    else:
        completed = []
    
    # Build checkpoint structure
    checkpoint = {
        "ticker": ticker.upper(),
        "saved_at": datetime.now().isoformat(),
        "completed_phases": completed,
        "current_phase": phase,
        "data": data
    }
    
    # Atomic write: temp file + rename
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=CHECKPOINT_DIR,
            prefix="checkpoint_tmp_",
            suffix=".json",
            delete=False
        ) as tmp_file:
            json.dump(checkpoint, tmp_file, ensure_ascii=False, indent=2)
            tmp_path = tmp_file.name
        
        os.rename(tmp_path, checkpoint_path)
        return True
    except Exception as e:
        # Clean up temp file if it exists
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except Exception:
            pass
        return False


def load_checkpoint(ticker: str) -> Optional[dict]:
    """
    Load a checkpoint for the given ticker.
    
    Args:
        ticker: Stock ticker symbol
    
    Returns:
        Checkpoint dict with ticker, saved_at, completed_phases, current_phase, data
        or None if no checkpoint exists
    """
    checkpoint_path = _get_checkpoint_path(ticker)
    
    if not os.path.exists(checkpoint_path):
        return None
    
    try:
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def clear_checkpoint(ticker: str) -> bool:
    """
    Clear (delete) the checkpoint for a ticker after successful completion.
    
    Args:
        ticker: Stock ticker symbol
    
    Returns:
        True if cleared or didn't exist, False on error
    """
    checkpoint_path = _get_checkpoint_path(ticker)
    
    if not os.path.exists(checkpoint_path):
        return True
    
    try:
        os.unlink(checkpoint_path)
        return True
    except Exception:
        return False


def get_checkpoint_phase(ticker: str) -> Optional[str]:
    """
    Get the current phase from a checkpoint without loading full data.
    
    Args:
        ticker: Stock ticker symbol
    
    Returns:
        Current phase string or None if no checkpoint
    """
    checkpoint = load_checkpoint(ticker)
    if checkpoint:
        return checkpoint.get("current_phase")
    return None


def mark_phase_complete(ticker: str, phase: str) -> bool:
    """
    Mark a phase as completed in the checkpoint. Call this after a phase
    finishes successfully, before starting the next phase.
    
    Args:
        ticker: Stock ticker symbol
        phase: Phase name to mark as completed
    
    Returns:
        True if update succeeded
    """
    checkpoint = load_checkpoint(ticker)
    if not checkpoint:
        return False
    
    completed = checkpoint.get("completed_phases", [])
    if phase not in completed:
        completed.append(phase)
    
    checkpoint["completed_phases"] = completed
    checkpoint["saved_at"] = datetime.now().isoformat()
    
    # Re-save with updated completed list
    checkpoint_path = _get_checkpoint_path(ticker)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=CHECKPOINT_DIR,
            prefix="checkpoint_tmp_",
            suffix=".json",
            delete=False
        ) as tmp_file:
            json.dump(checkpoint, tmp_file, ensure_ascii=False, indent=2)
            tmp_path = tmp_file.name
        
        os.rename(tmp_path, checkpoint_path)
        return True
    except Exception:
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except Exception:
            pass
        return False


def get_completed_phases(ticker: str) -> list:
    """
    Get list of completed phases for a ticker.
    
    Args:
        ticker: Stock ticker symbol
    
    Returns:
        List of completed phase names, empty list if no checkpoint
    """
    checkpoint = load_checkpoint(ticker)
    if checkpoint:
        return checkpoint.get("completed_phases", [])
    return []
