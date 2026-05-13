#!/usr/bin/env python3
"""
Stock_Team_Agent 共識引擎
整合7位分析師的結果，產生共識建議

共識機制：
1. 權重計算 - 不同分析師在不同任務類型有不同權重
2. 衝突檢測 - 識別並處理分析師之間的分歧
3. 共識閾值 - 達到閾值才產生強共識
4. 多維度評分 - 買入/賣出/持有多維度評分
"""

import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# Pydantic schemas (optional - graceful fallback if not installed)
try:
    from schemas import (
        ConsensusResult, AnalystScores, WeightedScores, ConflictRecord,
        SignalType, Confidence
    )
    SCHEMAS_AVAILABLE = True
except ImportError:
    SCHEMAS_AVAILABLE = False


class ConsensusEngine:
    """
    多分析師共識引擎
    
    支援：
    - 動態權重調整
    - 衝突檢測與解決
    - 多維度評分
    - 共識信心度計算
    """
    
    def __init__(self):
        # 分析師權重配置（可動態調整）
        self.analyst_weights = {
            "market": {"full": 1.0, "technical": 1.2, "fundamental": 0.5, "risk": 0.8, "sentiment": 0.8, "macro": 0.7, "news": 0.5},
            "technical": {"full": 1.0, "technical": 1.5, "fundamental": 0.5, "risk": 0.6, "sentiment": 0.4, "macro": 0.5, "news": 0.3},
            "fundamental": {"full": 1.0, "technical": 0.5, "fundamental": 1.5, "risk": 1.0, "sentiment": 0.5, "macro": 0.6, "news": 0.4},
            "risk": {"full": 1.2, "technical": 0.8, "fundamental": 1.0, "risk": 1.5, "sentiment": 0.6, "macro": 0.8, "news": 0.5},
            "sentiment": {"full": 0.8, "technical": 0.4, "fundamental": 0.5, "risk": 0.5, "sentiment": 1.5, "macro": 0.5, "news": 0.7},
            "macro": {"full": 0.8, "technical": 0.5, "fundamental": 0.6, "risk": 0.8, "sentiment": 0.5, "macro": 1.2, "news": 0.6},
            "news": {"full": 0.7, "technical": 0.3, "fundamental": 0.4, "risk": 0.5, "sentiment": 0.7, "macro": 0.6, "news": 1.2},
        }
        
        # 共識閾值
        self.consensus_threshold = 0.6  # 60%以上共識為強共識
        self.min_analysts = 4  # 最少需要4位分析師（7位中至少過半）
        
        # 評分維度
        self.dimensions = ["buy", "hold", "sell"]
        
    def integrate(self, analyst_results: Dict[str, Dict], task_type: str, symbol: str) -> Dict[str, Any]:
        """
        主整合函數：整合多位分析師的結果
        
        Args:
            analyst_results: {analyst_name: result_dict}
            task_type: 任務類型
            symbol: 股票代碼
            
        Returns:
            共識結果字典
        """
        if len(analyst_results) < self.min_analysts:
            return {"error": "分析師數量不足", "status": "insufficient"}
        
        # Step 1: 提取評分
        scores = self._extract_scores(analyst_results)
        
        # Step 2: 計算加權評分
        weighted_scores = self._calculate_weighted_scores(scores, task_type)
        
        # Step 3: 檢測衝突
        conflicts = self._detect_conflicts(analyst_results)
        
        # Step 4: 計算共識
        consensus = self._compute_consensus(weighted_scores)
        
        # Step 5: 產生建議
        recommendation = self._generate_recommendation(consensus, conflicts)
        
        # Step 6: 計算信心度
        confidence = self._calculate_confidence(analyst_results, consensus)
        
        return {
            "symbol": symbol,
            "task_type": task_type,
            "timestamp": datetime.now().isoformat(),
            "analyst_scores": scores,
            "weighted_scores": weighted_scores,
            "consensus": consensus,
            "conflicts": conflicts,
            "recommendation": recommendation,
            "confidence": confidence,
            "overall_score": consensus.get("overall", 0),
            "status": "success"
        }
    
    def _extract_scores(self, analyst_results: Dict[str, Dict]) -> Dict[str, Dict[str, float]]:
        """從每位分析師結果中提取評分"""
        scores = {}
        for analyst, result in analyst_results.items():
            if "error" in result:
                continue
            scores[analyst] = {
                "buy": result.get("buy_score", 0),
                "hold": result.get("hold_score", 0),
                "sell": result.get("sell_score", 0),
                "overall": result.get("score", 0),
                "confidence": result.get("confidence", 0.5),
            }
        return scores
    
    def _calculate_weighted_scores(self, scores: Dict[str, Dict], task_type: str) -> Dict[str, float]:
        """計算加權評分"""
        weighted = {"buy": 0, "hold": 0, "sell": 0}
        total_weight = 0
        
        for analyst, score in scores.items():
            weight = self.analyst_weights.get(analyst, {}).get(task_type, 1.0)
            for dim in self.dimensions:
                weighted[dim] += score[dim] * weight
            total_weight += weight
        
        if total_weight > 0:
            for dim in self.dimensions:
                weighted[dim] /= total_weight
        
        return weighted
    
    def _detect_conflicts(self, analyst_results: Dict[str, Dict]) -> List[Dict[str, Any]]:
        """檢測分析師之間的衝突"""
        conflicts = []
        
        # 比較不同分析師的信號
        signals = []
        for analyst, result in analyst_results.items():
            if "error" in result:
                continue
            signals.append({
                "analyst": analyst,
                "signal": result.get("signal", "neutral"),
                "score": result.get("score", 0)
            })
        
        # 檢測 Buy vs Sell 衝突
        buy_signals = [s for s in signals if s["signal"] in ["strong_buy", "buy"]]
        sell_signals = [s for s in signals if s["signal"] in ["strong_sell", "sell"]]
        
        if buy_signals and sell_signals:
            conflicts.append({
                "type": "buy_vs_sell",
                "buy_analysts": [s["analyst"] for s in buy_signals],
                "sell_analysts": [s["analyst"] for s in sell_signals],
                "severity": "high" if len(buy_signals) == len(sell_signals) else "medium"
            })
        
        # 檢測高分歧
        if len(signals) >= 3:
            scores = [s["score"] for s in signals if isinstance(s["score"], (int, float))]
            if scores:
                score_range = max(scores) - min(scores) if len(scores) > 1 else 0
                if score_range > 0.5:
                    conflicts.append({
                        "type": "high_divergence",
                        "score_range": score_range,
                        "severity": "high" if score_range > 0.7 else "medium"
                    })
        
        return conflicts
    
    def _compute_consensus(self, weighted_scores: Dict[str, float]) -> Dict[str, Any]:
        """計算共識"""
        total = sum(weighted_scores.values())
        
        if total == 0:
            return {"buy": 0, "hold": 0, "sell": 0, "overall": 0}
        
        normalized = {k: v/total for k, v in weighted_scores.items()}
        overall = (normalized.get("buy", 0) - normalized.get("sell", 0)) * 100
        
        return {
            "buy": round(normalized.get("buy", 0) * 100, 2),
            "hold": round(normalized.get("hold", 0) * 100, 2),
            "sell": round(normalized.get("sell", 0) * 100, 2),
            "overall": round(overall, 2)
        }
    
    def _generate_recommendation(self, consensus: Dict, conflicts: List) -> str:
        """根據共識產生建議"""
        buy = consensus.get("buy", 0)
        hold = consensus.get("hold", 0)
        sell = consensus.get("sell", 0)
        
        # 基本邏輯
        if buy > 60:
            recommendation = "強烈買入"
        elif buy > 40:
            recommendation = "適度買入"
        elif sell > 60:
            recommendation = "強烈賣出"
        elif sell > 40:
            recommendation = "適度賣出"
        elif hold > 50:
            recommendation = "持有觀望"
        else:
            recommendation = "中性觀望"
        
        # 衝突降級
        if any(c["type"] == "buy_vs_sell" and c["severity"] == "high" for c in conflicts):
            recommendation += "（分析師存在重大分歧，建議謹慎）"
        elif any(c["type"] == "high_divergence" and c["severity"] == "high" for c in conflicts):
            recommendation += "（分數分歧較大）"
        
        return recommendation
    
    def _calculate_confidence(self, analyst_results: Dict, consensus: Dict) -> float:
        """計算共識信心度"""
        # 基於分析師數量
        analyst_count = len([r for r in analyst_results.values() if "error" not in r])
        count_factor = min(analyst_count / 7, 1.0)  # 7位分析師為滿分
        
        # 基於評分一致性
        raw_scores = [r.get("score", 0) for r in analyst_results.values() if "error" not in r]
        scores = [s for s in raw_scores if isinstance(s, (int, float))]
        if len(scores) >= 2:
            mean_score = sum(scores) / len(scores)
            score_variance = sum((s - mean_score)**2 for s in scores) / len(scores)
            consistency_factor = max(0, 1 - score_variance)
        else:
            consistency_factor = 0.5
        
        # 基於評分強度
        strength = abs(consensus.get("overall", 0)) / 100
        
        confidence = (count_factor * 0.4 + consistency_factor * 0.3 + strength * 0.3)
        return round(confidence, 2)
    
    def update_weights(self, analyst: str, task_type: str, weight: float):
        """動態更新權重"""
        if analyst not in self.analyst_weights:
            self.analyst_weights[analyst] = {}
        self.analyst_weights[analyst][task_type] = weight
    
    def get_consensus_history(self) -> List[Dict]:
        """獲取共識歷史"""
        return getattr(self, "history", [])

    def integrate_pydantic(self, analyst_results: Dict[str, Dict], task_type: str, symbol: str) -> "ConsensusResult":
        """整合並返回 Pydantic 模型（需要 pydantic）。

        Returns:
            ConsensusResult Pydantic model (or raises if schemas not available)
        """
        if not SCHEMAS_AVAILABLE:
            raise ImportError("Pydantic schemas not available. Install or use integrate() instead.")

        # Use original integrate
        raw_result = self.integrate(analyst_results, task_type, symbol)

        # Build Pydantic models
        analyst_scores = {}
        for name, scores in raw_result["analyst_scores"].items():
            analyst_scores[name] = AnalystScores(**scores)

        weighted = WeightedScores(**raw_result["weighted_scores"])

        consensus_pct = {
            "buy": raw_result["consensus"]["buy"],
            "hold": raw_result["consensus"]["hold"],
            "sell": raw_result["consensus"]["sell"],
        }

        conflicts = []
        for c in raw_result.get("conflicts", []):
            conflicts.append(ConflictRecord(
                type=c.get("type", "unknown"),
                analysts_involved=c.get("buy_analysts", []) + c.get("sell_analysts", []),
                details=str(c),
                severity=c.get("severity", "medium"),
            ))

        # Determine signal strength (5-tier)
        overall = raw_result["overall_score"]
        if overall >= 60:
            signal_strength = 5  # STRONG_BUY
        elif overall >= 30:
            signal_strength = 4  # BUY
        elif overall >= -30:
            signal_strength = 3  # HOLD
        elif overall >= -60:
            signal_strength = 2  # SELL
        else:
            signal_strength = 1  # STRONG_SELL

        confidence_val = raw_result["confidence"]
        if confidence_val >= 0.75:
            conf_label = "high"
        elif confidence_val >= 0.50:
            conf_label = "medium"
        else:
            conf_label = "low"

        return ConsensusResult(
            symbol=symbol,
            task_type=task_type,
            timestamp=datetime.now(),
            analyst_scores=analyst_scores,
            weighted_scores=weighted,
            consensus_pct=consensus_pct,
            overall_score=overall,
            conflicts=conflicts,
            recommendation=raw_result["recommendation"],
            signal_strength=signal_strength,
            confidence=confidence_val,
            confidence_label=conf_label,
            status="success",
        )


def main():
    """測試函數"""
    engine = ConsensusEngine()
    
    # 模擬5位分析師結果
    test_results = {
        "market": {"signal": "buy", "score": 0.75, "buy_score": 0.7, "hold_score": 0.2, "sell_score": 0.1, "confidence": 0.8},
        "technical": {"signal": "buy", "score": 0.8, "buy_score": 0.8, "hold_score": 0.15, "sell_score": 0.05, "confidence": 0.9},
        "fundamental": {"signal": "hold", "score": 0.5, "buy_score": 0.4, "hold_score": 0.4, "sell_score": 0.2, "confidence": 0.6},
        "risk": {"signal": "sell", "score": 0.3, "buy_score": 0.2, "hold_score": 0.3, "sell_score": 0.5, "confidence": 0.7},
        "sentiment": {"signal": "buy", "score": 0.7, "buy_score": 0.6, "hold_score": 0.3, "sell_score": 0.1, "confidence": 0.75},
    }
    
    result = engine.integrate(test_results, "full_analysis", "0700.HK")
    
    print("=" * 60)
    print("共識引擎測試結果")
    print("=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
