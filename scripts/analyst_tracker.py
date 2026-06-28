#!/usr/bin/env python3
"""
Analyst Score Persistence Tracker for Stock Team Agent

Tracks analyst ratings over time to detect rating drift, consistency,
and performance. Stores data in ~/.hermes/stock_memory/analyst_tracker/

Provides:
- Persistent storage of individual analyst scores per symbol
- Rating history with timestamps
- Signal change detection
- Analyst consistency statistics
- Rating drift alerts
"""

import json
import sqlite3
import os
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager

DEFAULT_TRACKER_DIR = Path.home() / ".hermes" / "stock_memory" / "analyst_tracker"


class AnalystTracker:
    """
    Persistent analyst score tracker with SQLite index + JSON records.
    
    Tracks individual analyst ratings over time to enable:
    - Rating history per symbol
    - Signal change detection
    - Analyst consistency metrics
    - Rating drift alerts
    """

    def __init__(self, tracker_dir: Path = DEFAULT_TRACKER_DIR):
        self.tracker_dir = Path(tracker_dir)
        self.db_path = self.tracker_dir / "analyst_tracker.db"
        self.records_dir = self.tracker_dir / "records"
        self.tracker_dir.mkdir(parents=True, exist_ok=True)
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database schema."""
        with self._get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analyst_ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rating_id TEXT UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    analyst TEXT NOT NULL,
                    signal TEXT NOT NULL,
                    score REAL NOT NULL,
                    buy_score REAL,
                    hold_score REAL,
                    sell_score REAL,
                    confidence REAL,
                    summary TEXT,
                    timestamp TEXT NOT NULL,
                    json_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON analyst_ratings(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_analyst ON analyst_ratings(analyst)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON analyst_ratings(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_analyst ON analyst_ratings(symbol, analyst)")
            conn.commit()

    @contextmanager
    def _get_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def log_rating(
        self,
        symbol: str,
        analyst: str,
        signal: str,
        score: float,
        buy_score: Optional[float] = None,
        hold_score: Optional[float] = None,
        sell_score: Optional[float] = None,
        confidence: Optional[float] = None,
        summary: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Log an analyst rating for a symbol.
        
        Args:
            symbol: Stock ticker symbol (e.g., "0700.HK")
            analyst: Analyst identifier (e.g., "technical", "fundamental")
            signal: Signal type (buy/sell/neutral/strong_buy/strong_sell)
            score: Overall score 0-1
            buy_score: Buy probability 0-1
            hold_score: Hold probability 0-1
            sell_score: Sell probability 0-1
            confidence: Confidence level 0-1
            summary: Analyst summary text
            extra_data: Additional data to store
            
        Returns:
            rating_id: Unique identifier for this rating
        """
        rating_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        json_path = self.records_dir / (rating_id + ".json")
        record = {
            "rating_id": rating_id,
            "symbol": symbol.upper(),
            "analyst": analyst,
            "signal": signal,
            "score": score,
            "buy_score": buy_score,
            "hold_score": hold_score,
            "sell_score": sell_score,
            "confidence": confidence,
            "summary": summary,
            "timestamp": timestamp,
            "extra_data": extra_data or {},
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        with self._get_db() as conn:
            conn.execute("""
                INSERT INTO analyst_ratings (
                    rating_id, symbol, analyst, signal, score,
                    buy_score, hold_score, sell_score, confidence, summary,
                    timestamp, json_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rating_id, symbol.upper(), analyst, signal, score,
                buy_score, hold_score, sell_score, confidence, summary,
                timestamp, str(json_path),
            ))
            conn.commit()

        return rating_id

    def log_analyst_results(self, symbol: str, analyst_results: Dict[str, Dict]) -> List[str]:
        """
        Log multiple analyst results at once (e.g., from a consensus run).
        
        Args:
            symbol: Stock ticker symbol
            analyst_results: Dict of {analyst_name: result_dict}
            
        Returns:
            List of rating_ids created
        """
        rating_ids = []
        for analyst, result in analyst_results.items():
            if "error" in result:
                continue
            rating_id = self.log_rating(
                symbol=symbol,
                analyst=analyst,
                signal=result.get("signal", "neutral"),
                score=result.get("score", 0),
                buy_score=result.get("buy_score"),
                hold_score=result.get("hold_score"),
                sell_score=result.get("sell_score"),
                confidence=result.get("confidence"),
                summary=result.get("summary"),
                extra_data=result,
            )
            rating_ids.append(rating_id)
        return rating_ids

    # ========================================================================
    # v5.10 (Stage 4.5b) DEPRECATED GETTERS — no caller in stock-team-agent
    # ========================================================================
    # 下列 11 個 methods 在 stock-team-agent 內 0 external caller (僅 CLI main() 使用)
    # 若用戶手動跑 `python analyst_tracker.py --symbol AAPL --history` 等指令仍可用
    # 若需移除，先確認 main() 是否仍被外部 cron/job 調用
    # ========================================================================

    def get_symbol_history(  # noqa: kept for CLI backward compat
        self,
        symbol: str,
        analyst: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get rating history for a symbol.
        
        Args:
            symbol: Stock ticker symbol
            analyst: Optional filter by specific analyst
            limit: Maximum number of records to return
            
        Returns:
            List of rating records, newest first
        """
        with self._get_db() as conn:
            if analyst:
                rows = conn.execute("""
                    SELECT * FROM analyst_ratings
                    WHERE symbol = ? AND analyst = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (symbol.upper(), analyst, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM analyst_ratings
                    WHERE symbol = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (symbol.upper(), limit)).fetchall()

        results = []
        for row in rows:
            record = dict(row)
            json_path = record.get("json_path")
            if json_path and os.path.exists(json_path):
                with open(json_path, encoding="utf-8") as f:
                    full_record = json.load(f)
                    results.append(full_record)
            else:
                results.append(record)
        return results

    def get_latest_ratings(self, symbol: str) -> Dict[str, Dict]:
        """
        Get the latest rating from each analyst for a symbol.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Dict of {analyst: latest_rating_dict}
        """
        with self._get_db() as conn:
            rows = conn.execute("""
                SELECT r1.* FROM analyst_ratings r1
                INNER JOIN (
                    SELECT analyst, MAX(timestamp) as max_ts
                    FROM analyst_ratings
                    WHERE symbol = ?
                    GROUP BY analyst
                ) r2 ON r1.analyst = r2.analyst AND r1.timestamp = r2.max_ts
                WHERE r1.symbol = ?
            """, (symbol.upper(), symbol.upper())).fetchall()

        latest = {}
        for row in rows:
            record = dict(row)
            json_path = record.get("json_path")
            if json_path and os.path.exists(json_path):
                with open(json_path, encoding="utf-8") as f:
                    latest[record["analyst"]] = json.load(f)
            else:
                latest[record["analyst"]] = record
        return latest

    def get_signal_changes(
        self,
        symbol: str,
        analyst: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Detect signal changes for a symbol over time.
        
        Args:
            symbol: Stock ticker symbol
            analyst: Optional filter by specific analyst
            limit: Maximum number of changes to return
            
        Returns:
            List of signal change records
        """
        history = self.get_symbol_history(symbol, analyst=analyst, limit=limit * 2)
        
        changes = []
        prev_record = None
        for record in history:
            if prev_record and record["analyst"] == prev_record["analyst"]:
                if record["signal"] != prev_record["signal"]:
                    changes.append({
                        "symbol": symbol,
                        "analyst": record["analyst"],
                        "from_signal": prev_record["signal"],
                        "to_signal": record["signal"],
                        "from_score": prev_record["score"],
                        "to_score": record["score"],
                        "change_time": record["timestamp"],
                        "previous_time": prev_record["timestamp"],
                    })
            prev_record = record
            if len(changes) >= limit:
                break
        return changes

    def get_analyst_consistency(
        self,
        analyst: str,
        symbol: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate consistency metrics for an analyst.
        
        Args:
            analyst: Analyst identifier
            symbol: Optional filter by symbol
            days: Lookback period in days
            
        Returns:
            Dict with consistency metrics
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self._get_db() as conn:
            if symbol:
                rows = conn.execute("""
                    SELECT score, signal FROM analyst_ratings
                    WHERE analyst = ? AND symbol = ? AND timestamp >= ?
                    ORDER BY timestamp
                """, (analyst, symbol.upper(), cutoff_date)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT score, signal FROM analyst_ratings
                    WHERE analyst = ? AND timestamp >= ?
                    ORDER BY timestamp
                """, (analyst, cutoff_date)).fetchall()

        if not rows:
            return {
                "analyst": analyst,
                "sample_size": 0,
                "consistency_score": 0,
                "avg_score": 0,
                "score_stddev": 0,
            }

        scores = [r["score"] for r in rows if r["score"] is not None]
        
        if len(scores) < 2:
            return {
                "analyst": analyst,
                "sample_size": len(scores),
                "consistency_score": 1.0 if scores else 0,
                "avg_score": scores[0] if scores else 0,
                "score_stddev": 0,
            }

        avg_score = sum(scores) / len(scores)
        variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
        stddev = variance ** 0.5
        
        # Consistency: lower variance = higher consistency
        # Normalize stddev (max expected ~0.5) to 0-1 range
        consistency_score = max(0, 1 - (stddev / 0.5)) if stddev <= 0.5 else 0

        return {
            "analyst": analyst,
            "sample_size": len(scores),
            "consistency_score": round(consistency_score, 3),
            "avg_score": round(avg_score, 3),
            "score_stddev": round(stddev, 3),
            "signals": [r["signal"] for r in rows],
        }

    def get_rating_drift(
        self,
        symbol: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Detect rating drift for a symbol across all analysts.
        
        Args:
            symbol: Stock ticker symbol
            days: Lookback period in days
            
        Returns:
            Dict with drift metrics per analyst
        """
        latest = self.get_latest_ratings(symbol)
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        drift_data = {}
        for analyst, latest_record in latest.items():
            history = self.get_symbol_history(symbol, analyst=analyst, limit=100)
            
            # Filter to lookback period
            history = [r for r in history if r.get("timestamp", "") >= cutoff_date]
            
            if len(history) < 2:
                continue
            
            first_record = history[-1]  # oldest in filtered set
            current_record = latest_record
            
            score_change = current_record.get("score", 0) - first_record.get("score", 0)
            signal_changed = current_record.get("signal") != first_record.get("signal")
            
            drift_data[analyst] = {
                "current_score": current_record.get("score", 0),
                "first_score": first_record.get("score", 0),
                "score_change": round(score_change, 3),
                "signal_changed": signal_changed,
                "from_signal": first_record.get("signal"),
                "to_signal": current_record.get("signal"),
                "sample_count": len(history),
            }
        
        return drift_data

    def get_all_symbols(self) -> List[str]:
        """Get all symbols that have been tracked."""
        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT DISTINCT symbol FROM analyst_ratings ORDER BY symbol"
            ).fetchall()
        return [r["symbol"] for r in rows]

    def get_all_analysts(self) -> List[str]:
        """Get all analysts that have been tracked."""
        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT DISTINCT analyst FROM analyst_ratings ORDER BY analyst"
            ).fetchall()
        return [r["analyst"] for r in rows]

    def get_stats(self) -> Dict[str, Any]:
        """Get overall tracker statistics."""
        with self._get_db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM analyst_ratings").fetchone()[0]
            
            by_analyst = {}
            for row in conn.execute(
                "SELECT analyst, COUNT(*) as count FROM analyst_ratings GROUP BY analyst"
            ):
                by_analyst[row["analyst"]] = row["count"]
            
            by_signal = {}
            for row in conn.execute(
                "SELECT signal, COUNT(*) as count FROM analyst_ratings GROUP BY signal"
            ):
                by_signal[row["signal"]] = row["count"]
            
            by_symbol_count = {}
            for row in conn.execute("""
                SELECT symbol, COUNT(*) as count FROM analyst_ratings
                GROUP BY symbol ORDER BY count DESC LIMIT 10
            """):
                by_symbol_count[row["symbol"]] = row["count"]
            
            date_range_query = """
                SELECT MIN(timestamp) as earliest, MAX(timestamp) as latest
                FROM analyst_ratings
            """
            date_row = conn.execute(date_range_query).fetchone()
            
        return {
            "total_ratings": total,
            "by_analyst": by_analyst,
            "by_signal": by_signal,
            "top_symbols": by_symbol_count,
            "earliest_record": date_row["earliest"] if date_row else None,
            "latest_record": date_row["latest"] if date_row else None,
        }

    def get_analyst_performance(
        self,
        analyst: str,
        days: int = 90
    ) -> Dict[str, Any]:
        """
        Get performance metrics for an analyst over time.
        
        Args:
            analyst: Analyst identifier
            days: Lookback period
            
        Returns:
            Dict with performance metrics
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self._get_db() as conn:
            rows = conn.execute("""
                SELECT * FROM analyst_ratings
                WHERE analyst = ? AND timestamp >= ?
                ORDER BY timestamp
            """, (analyst, cutoff_date)).fetchall()

        if not rows:
            return {
                "analyst": analyst,
                "period_days": days,
                "total_ratings": 0,
                "avg_confidence": 0,
            }

        scores = [r["score"] for r in rows if r["score"] is not None]
        confidences = [r["confidence"] for r in rows if r["confidence"] is not None]
        
        signals = {}
        for r in rows:
            sig = r["signal"]
            signals[sig] = signals.get(sig, 0) + 1
        
        return {
            "analyst": analyst,
            "period_days": days,
            "total_ratings": len(rows),
            "avg_score": round(sum(scores) / len(scores), 3) if scores else 0,
            "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
            "score_range": {
                "min": round(min(scores), 3) if scores else 0,
                "max": round(max(scores), 3) if scores else 0,
            },
            "signal_distribution": signals,
        }

    def clear_old_records(self, days: int = 365) -> int:
        """
        Clear records older than specified days.
        
        Args:
            days: Delete records older than this many days
            
        Returns:
            Number of records deleted
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self._get_db() as conn:
            # Get json paths to delete
            rows = conn.execute(
                "SELECT json_path FROM analyst_ratings WHERE timestamp < ?",
                (cutoff_date,)
            ).fetchall()
            
            # Delete JSON files
            deleted_files = 0
            for row in rows:
                json_path = row["json_path"]
                if json_path and os.path.exists(json_path):
                    try:
                        os.unlink(json_path)
                        deleted_files += 1
                    except OSError:
                        pass
            
            # Delete from database
            cursor = conn.execute(
                "DELETE FROM analyst_ratings WHERE timestamp < ?",
                (cutoff_date,)
            )
            conn.commit()
            
        return cursor.rowcount


def main():
    """CLI entry point for analyst tracker."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyst Score Persistence Tracker")
    parser.add_argument("--symbol", "-s", help="Stock ticker symbol")
    parser.add_argument("--analyst", "-a", help="Analyst name")
    parser.add_argument("--history", action="store_true", help="Show rating history")
    parser.add_argument("--latest", action="store_true", help="Show latest ratings")
    parser.add_argument("--changes", action="store_true", help="Show signal changes")
    parser.add_argument("--consistency", action="store_true", help="Show analyst consistency")
    parser.add_argument("--drift", action="store_true", help="Show rating drift")
    parser.add_argument("--stats", action="store_true", help="Show overall stats")
    parser.add_argument("--performance", action="store_true", help="Show analyst performance")
    parser.add_argument("--days", type=int, default=30, help="Days for lookback")
    parser.add_argument("--limit", type=int, default=20, help="Limit results")
    
    args = parser.parse_args()
    
    tracker = AnalystTracker()
    
    if args.stats:
        print("=" * 60)
        print("Analyst Tracker Statistics")
        print("=" * 60)
        stats = tracker.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return
    
    if args.symbol and args.latest:
        print("=" * 60)
        print(f"Latest Ratings: {args.symbol}")
        print("=" * 60)
        latest = tracker.get_latest_ratings(args.symbol)
        print(json.dumps(latest, indent=2, ensure_ascii=False))
        return
    
    if args.symbol and args.history:
        print("=" * 60)
        print(f"Rating History: {args.symbol}")
        print("=" * 60)
        history = tracker.get_symbol_history(
            args.symbol,
            analyst=args.analyst,
            limit=args.limit
        )
        for record in history:
            print(f"[{record['timestamp']}] {record['analyst']}: {record['signal']} ({record['score']:.2f})")
        return
    
    if args.symbol and args.changes:
        print("=" * 60)
        print(f"Signal Changes: {args.symbol}")
        print("=" * 60)
        changes = tracker.get_signal_changes(args.symbol, analyst=args.analyst, limit=args.limit)
        for change in changes:
            print(f"[{change['change_time']}] {change['analyst']}: {change['from_signal']} → {change['to_signal']}")
        return
    
    if args.analyst and args.consistency:
        print("=" * 60)
        print(f"Analyst Consistency: {args.analyst}")
        print("=" * 60)
        consistency = tracker.get_analyst_consistency(args.analyst, symbol=args.symbol, days=args.days)
        print(json.dumps(consistency, indent=2, ensure_ascii=False))
        return
    
    if args.symbol and args.drift:
        print("=" * 60)
        print(f"Rating Drift: {args.symbol}")
        print("=" * 60)
        drift = tracker.get_rating_drift(args.symbol, days=args.days)
        print(json.dumps(drift, indent=2, ensure_ascii=False))
        return
    
    if args.analyst and args.performance:
        print("=" * 60)
        print(f"Analyst Performance: {args.analyst}")
        print("=" * 60)
        perf = tracker.get_analyst_performance(args.analyst, days=args.days)
        print(json.dumps(perf, indent=2, ensure_ascii=False))
        return
    
    # Default: show all symbols and stats
    print("=" * 60)
    print("Analyst Tracker Overview")
    print("=" * 60)
    symbols = tracker.get_all_symbols()
    analysts = tracker.get_all_analysts()
    print(f"Tracked symbols: {len(symbols)}")
    print(f"Tracked analysts: {len(analysts)}")
    print(f"Symbols: {', '.join(symbols[:10])}{'...' if len(symbols) > 10 else ''}")
    print(f"Analysts: {', '.join(analysts)}")
    print()
    print("Use --help for full usage information")


if __name__ == "__main__":
    main()
