"""
Persistent Decision Log for Stock Team Agent
Provides persistent memory across analysis sessions.
Stores decisions to ~/.hermes/stock_memory/
"""

import json
import sqlite3
import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

DEFAULT_MEMORY_DIR = Path.home() / ".hermes" / "stock_memory"


class DecisionLogger:
    """Persistent decision log with SQLite index + JSON records."""

    def __init__(self, memory_dir: Path = DEFAULT_MEMORY_DIR):
        self.memory_dir = Path(memory_dir)
        self.db_path = self.memory_dir / "decisions.db"
        self.decisions_dir = self.memory_dir / "decisions"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.decisions_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_id TEXT UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    signal_strength INTEGER,
                    confidence REAL,
                    rationale TEXT,
                    timestamp TEXT NOT NULL,
                    consensus_pct_buy REAL,
                    consensus_pct_hold REAL,
                    consensus_pct_sell REAL,
                    overall_score REAL,
                    analysts_count INTEGER,
                    has_conflicts INTEGER DEFAULT 0,
                    json_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON decisions(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON decisions(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_action ON decisions(action)")
            conn.commit()

    @contextmanager
    def _get_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def log_decision(
        self,
        symbol: str,
        action: str,
        rationale: str,
        confidence: float,
        overall_score: float,
        consensus_pct: Optional[Dict[str, float]] = None,
        signal_strength: Optional[int] = None,
        analysts_count: Optional[int] = None,
        has_conflicts: bool = False,
        consensus_result: Optional[Any] = None,
        extra_data: Optional[Dict] = None,
    ) -> str:
        decision_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        json_path = self.decisions_dir / (decision_id + ".json")
        record = {
            "decision_id": decision_id,
            "symbol": symbol,
            "action": action,
            "signal_strength": signal_strength,
            "confidence": confidence,
            "overall_score": overall_score,
            "rationale": rationale,
            "timestamp": timestamp,
            "consensus_pct": consensus_pct or {},
            "analysts_count": analysts_count,
            "has_conflicts": has_conflicts,
            "extra_data": extra_data or {},
        }

        if consensus_result is not None:
            if hasattr(consensus_result, "model_dump"):
                record["consensus"] = consensus_result.model_dump()
            elif hasattr(consensus_result, "to_dict"):
                record["consensus"] = consensus_result.to_dict()

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO decisions (
                    decision_id, symbol, action, signal_strength, confidence,
                    rationale, timestamp, consensus_pct_buy, consensus_pct_hold,
                    consensus_pct_sell, overall_score, analysts_count, has_conflicts, json_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                decision_id, symbol, action, signal_strength, confidence,
                rationale[:500] if rationale else None, timestamp,
                consensus_pct.get("buy") if consensus_pct else None,
                consensus_pct.get("hold") if consensus_pct else None,
                consensus_pct.get("sell") if consensus_pct else None,
                overall_score, analysts_count, 1 if has_conflicts else 0, str(json_path),
            ))
            conn.commit()

        return decision_id

    def get_symbol_history(self, symbol: str, limit: int = 20) -> List[Dict]:
        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM decisions WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?",
                (symbol.upper(), limit)
            ).fetchall()

        results = []
        for row in rows:
            record = dict(row)
            json_path = record.get("json_path")
            if json_path and os.path.exists(json_path):
                with open(json_path, encoding="utf-8") as f:
                    results.append(json.load(f))
            else:
                results.append(record)
        return results

    def get_recent(self, limit: int = 20, action: Optional[str] = None) -> List[Dict]:
        with self._get_db() as conn:
            if action:
                rows = conn.execute(
                    "SELECT * FROM decisions WHERE action = ? ORDER BY timestamp DESC LIMIT ?",
                    (action, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                ).fetchall()

        results = []
        for row in rows:
            record = dict(row)
            json_path = record.get("json_path")
            if json_path and os.path.exists(json_path):
                with open(json_path, encoding="utf-8") as f:
                    results.append(json.load(f))
            else:
                results.append(record)
        return results

    def get_stats(self) -> Dict[str, Any]:
        with self._get_db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]

            by_action = {}
            for row in conn.execute("SELECT action, COUNT(*) as count FROM decisions GROUP BY action"):
                by_action[row["action"]] = row["count"]

            by_symbol = {}
            query = "SELECT symbol, COUNT(*) as count FROM decisions GROUP BY symbol ORDER BY count DESC LIMIT 10"
            for row in conn.execute(query):
                by_symbol[row["symbol"]] = row["count"]

            avg_query = "SELECT AVG(confidence) FROM decisions WHERE confidence IS NOT NULL"
            avg_confidence = conn.execute(avg_query).fetchone()[0] or 0

            conflict_query = "SELECT COUNT(*) FROM decisions WHERE has_conflicts = 1"
            conflict_count = conn.execute(conflict_query).fetchone()[0]

        return {
            "total_decisions": total,
            "by_action": by_action,
            "top_symbols": by_symbol,
            "avg_confidence": round(avg_confidence, 3),
            "decisions_with_conflicts": conflict_count,
            "conflict_rate": round(conflict_count / total, 3) if total > 0 else 0,
        }

    def get_all_symbols(self) -> List[str]:
        with self._get_db() as conn:
            rows = conn.execute("SELECT DISTINCT symbol FROM decisions ORDER BY symbol").fetchall()
        return [r["symbol"] for r in rows]
