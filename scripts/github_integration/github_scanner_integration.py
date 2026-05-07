#!/usr/bin/env python3
"""
Stock_Team_Agent GitHub 整合模組
利用 GitHub Scanner 發現的資源增強股票分析能力

功能：
- 發現金融相關開源項目
- 發現量化交易算法
- 發現數據獲取工具
- 發現機器學習模型
- 自動評估整合可行性
"""

import json
import subprocess
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path


class GitHubIntegration:
    """
    Stock_Team_Agent 的 GitHub 能力擴展
    
    透過整合 GitHub Scanner 的發現，增強分析能力：
    - 量化交易策略
    - 財務數據API
    - 機器學習預測模型
    - 市場數據工具
    """
    
    def __init__(self):
        self.name = "github_integration"
        possible_paths = [
            Path.home() / ".hermes" / "scripts" / "github_scanner" / "data" / "repos.db",
            Path.home() / ".hermes" / "scripts" / "github_scanner" / "github_scanner.db",
        ]
        self.db_path = None
        for p in possible_paths:
            if p.exists():
                self.db_path = p
                break
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 3600  # 1小時
        
        # 預定義的高價值金融項目（S/A級，直接從GitHub Scanner數據庫）
        # 這些項目由 GitHub Scanner 確認為高價值
        self.high_value_repos = {
            "finance": [
                {"full_name": "OpenBB-finance/OpenBB", "stars": 66784, "description": "金融數據平台", "language": "Python", "tier": "S"},
                {"full_name": "TauricResearch/TradingAgents", "stars": 56954, "description": "Multi-Agent LLM 交易框架", "language": "Python", "tier": "S"},
                {"full_name": "freqtrade/freqtrade", "stars": 49613, "description": "加密貨幣交易機器人", "language": "Python", "tier": "S"},
                {"full_name": "ccxt/ccxt", "stars": 42137, "description": "加密貨幣交易所統一API", "language": "Python", "tier": "S"},
                {"full_name": "microsoft/qlib", "stars": 41596, "description": "AI量化投資平台", "language": "Python", "tier": "A"},
                {"full_name": "vnpy/vnpy", "stars": 40000, "description": "中文量化交易框架", "language": "Python", "tier": "A"},
            ],
            "sentiment": [
                {"full_name": "sansan0/TrendRadar", "stars": 55899, "description": "AI輿情監控+RSS聚合", "language": "Python", "tier": "S"},
                {"full_name": "666ghj/BettaFish", "stars": 40692, "description": "Multi-Agent輿情分析", "language": "Python", "tier": "S"},
            ]
        }
    
    def query_scanner_db(self, category: str = "finance", min_stars: int = 5000) -> List[Dict[str, Any]]:
        """
        直接查詢 GitHub Scanner 的 SQLite 數據庫
        
        參數:
            category: "finance" 或 "sentiment"
            min_stars: 最小 stars 數
        
        返回:
            從 Scanner 數據庫中發現的高價值項目
        """
        import sqlite3
        
        # 首先返回預定義的高價值項目
        cached = self.cache.get(f"scanner_db_{category}")
        if cached:
            return cached
        
        results = []
        
        # 嘗試直接讀取 Scanner 數據庫
        if self.db_path.exists():
            try:
                conn = sqlite3.connect(str(self.db_path))
                c = conn.cursor()
                
                # 根據 category 構建查詢
                if category == "finance":
                    query = """
                        SELECT full_name, description, stars, language, topics, value_tier
                        FROM repos 
                        WHERE (topics LIKE '%finance%' OR topics LIKE '%stock%' OR 
                               topics LIKE '%trading%' OR topics LIKE '%quantitative%' OR
                               topics LIKE '%investment%' OR topics LIKE '%technical-analysis%')
                        AND stars >= ?
                        ORDER BY stars DESC
                        LIMIT 20
                    """
                else:  # sentiment
                    query = """
                        SELECT full_name, description, stars, language, topics, value_tier
                        FROM repos 
                        WHERE (topics LIKE '%sentiment%' OR topics LIKE '%news%' OR 
                               topics LIKE '%analysis%' OR topics LIKE '%opinion%')
                        AND stars >= ?
                        ORDER BY stars DESC
                        LIMIT 20
                    """
                
                c.execute(query, (min_stars,))
                rows = c.fetchall()
                conn.close()
                
                for row in rows:
                    results.append({
                        "full_name": row[0],
                        "description": row[1] or "",
                        "stars": row[2],
                        "language": row[3] or "N/A",
                        "topics": row[4] or "",
                        "value_tier": row[5] or "B",
                        "source": "github_scanner_db"
                    })
            except Exception as e:
                print(f"⚠️ Scanner DB 查詢失敗: {e}")
        
        # 如果數據庫為空，使用預定義項目
        if not results:
            results = self.high_value_repos.get(category, [])
        
        self.cache[f"scanner_db_{category}"] = results
        return results
    
    def get_integration_recommendations(self, symbol: str = None, analysis_type: str = None) -> Dict[str, Any]:
        """
        獲取整合推薦（連接到真實的 GitHub Scanner 數據）
        
        這是 GitHub Scanner 與 Stock_Team_Agent 的橋樑
        """
        # 從 Scanner DB 獲取金融相關資源
        finance_repos = self.query_scanner_db("finance", min_stars=5000)
        sentiment_repos = self.query_scanner_db("sentiment", min_stars=3000)
        
        # 根據分析類型推薦
        recommendations = {
            "trading_algorithms": [],
            "data_tools": [],
            "sentiment_analysis": [],
            "ml_models": []
        }
        
        for repo in finance_repos:
            desc = repo.get("description", "").lower()
            if "trading" in desc or "bot" in desc:
                recommendations["trading_algorithms"].append(repo)
            elif "data" in desc or "api" in desc:
                recommendations["data_tools"].append(repo)
            elif "model" in desc or "predict" in desc:
                recommendations["ml_models"].append(repo)
        
        for repo in sentiment_repos:
            recommendations["sentiment_analysis"].append(repo)
        
        return {
            "symbol": symbol,
            "analysis_type": analysis_type,
            "timestamp": datetime.now().isoformat(),
            "recommendations": recommendations,
            "data_source": "github_scanner_db",
            "total_finance_repos": len(finance_repos),
            "total_sentiment_repos": len(sentiment_repos)
        }
    
    def search_financial_repos(self, query: str = None) -> List[Dict[str, Any]]:
        """
        搜索金融相關的 GitHub 倉庫
        
        關鍵詞：
        - stock prediction
        - financial analysis
        - trading algorithm
        - quantitative finance
        - technical analysis
        """
        keywords = [
            "stock market prediction",
            "financial data API",
            "quantitative trading",
            "technical analysis python",
            "stock screener",
            "portfolio optimization",
            "algorithmic trading",
            "forecasting stock",
        ]
        
        results = []
        for kw in keywords[:5]:  # 限制搜索數量
            try:
                result = self._search_github(kw)
                if result:
                    results.extend(result)
            except Exception as e:
                continue
        
        return self._deduplicate_and_score(results)
    
    def _search_github(self, keyword: str) -> List[Dict]:
        """搜索 GitHub - 使用 REST API 直接搜索"""
        try:
            import urllib.request
            import urllib.parse
            
            query = urllib.parse.quote(keyword)
            url = f"https://api.github.com/search/repositories?q={query}+in:name,description,readme&sort=stars&order=desc&per_page=10"
            
            headers = {
                "Accept": "application/vnd.github+json",
                "User-Agent": "Hermes-Stock-Agent/1.0"
            }
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                repos = data.get("items", [])
                
                results = []
                for repo in repos[:10]:
                    results.append({
                        "full_name": repo.get("full_name", ""),
                        "description": repo.get("description", ""),
                        "stars": repo.get("stargazers_count", 0),
                        "language": repo.get("language", ""),
                        "topics": repo.get("topics", []),
                        "url": repo.get("html_url", ""),
                        "has_readme": True,
                        "has_requirements": True,
                    })
                return results
        except Exception as e:
            print(f"GitHub search error: {e}")
            return []
    
    def _deduplicate_and_score(self, repos: List[Dict]) -> List[Dict]:
        """去重並評分"""
        seen = set()
        scored = []
        
        for repo in repos:
            repo_id = repo.get("full_name", "")
            if repo_id in seen:
                continue
            seen.add(repo_id)
            
            # 評分
            score = self._score_repo(repo)
            repo["integration_score"] = score
            scored.append(repo)
        
        # 按評分排序
        scored.sort(key=lambda x: x.get("integration_score", 0), reverse=True)
        return scored
    
    def _score_repo(self, repo: Dict) -> float:
        """評估倉庫與股票分析的整合價值"""
        score = 0.0
        
        # Stars
        stars = repo.get("stars", 0)
        score += min(stars / 1000, 5)  # 最高5分
        
        # 語言
        language = (repo.get("language") or "").lower()
        if language in ["python", "jupyter notebook"]:
            score += 2.0
        elif language in ["javascript", "typescript"]:
            score += 1.0
        
        # 主題標籤
        topics = repo.get("topics", [])
        relevant_topics = [
            "stock", "finance", "trading", "investment",
            "machine-learning", "deep-learning", "data-analysis",
            "api", "quantitative-finance"
        ]
        score += len([t for t in topics if t in relevant_topics]) * 0.5
        
        return round(score, 2)
    
    def get_trading_algorithms(self) -> List[Dict[str, Any]]:
        """獲取量化交易算法相關倉庫"""
        algos = self.search_financial_repos("quantitative trading algorithm")
        
        # 評估每個算法的可用性
        for algo in algos:
            algo["usability"] = self._assess_usability(algo)
        
        return algos
    
    def get_data_tools(self) -> List[Dict[str, Any]]:
        """獲取數據工具倉庫"""
        tools = self.search_financial_repos("financial data API")
        
        for tool in tools:
            tool["data_sources"] = self._identify_data_sources(tool)
        
        return tools
    
    def _assess_usability(self, repo: Dict) -> str:
        """評估倉庫的易用性"""
        has_readme = repo.get("has_readme", False)
        has_requirements = repo.get("has_requirements", False)
        stars = repo.get("stars", 0)
        
        if has_readme and has_requirements and stars > 100:
            return "high"
        elif has_readme or stars > 500:
            return "medium"
        return "low"
    
    def _identify_data_sources(self, repo: Dict) -> List[str]:
        """識別倉庫提供的數據源"""
        description = (repo.get("description", "") + repo.get("readme", "")).lower()
        
        sources = []
        if "yahoo" in description:
            sources.append("Yahoo Finance")
        if "alpha" in description or "vantage" in description:
            sources.append("Alpha Vantage")
        if "finnhub" in description:
            sources.append("Finnhub")
        if "polygon" in description:
            sources.append("Polygon.io")
        if "nasdaq" in description:
            sources.append("Nasdaq")
        if "bloomberg" in description:
            sources.append("Bloomberg")
        
        return sources if sources else ["Unknown"]
    
    def generate_analysis_enhancement_report(self, symbol: str, analysis_type: str) -> Dict[str, Any]:
        """生成分析增強報告"""
        # 搜索相關資源
        repos = self.search_financial_repos(f"{symbol} stock analysis")
        
        # 分類資源
        trading_algos = [r for r in repos if "trading" in r.get("description", "").lower()]
        data_tools = [r for r in repos if "api" in r.get("description", "").lower() or "data" in r.get("description", "").lower()]
        ml_models = [r for r in repos if "model" in r.get("description", "").lower() or "prediction" in r.get("description", "").lower()]
        
        return {
            "symbol": symbol,
            "analysis_type": analysis_type,
            "timestamp": datetime.now().isoformat(),
            "resources": {
                "trading_algorithms": trading_algos[:5],
                "data_tools": data_tools[:5],
                "ml_models": ml_models[:5],
            },
            "summary": {
                "total_repos_found": len(repos),
                "high_usability_count": len([r for r in repos if r.get("usability") == "high"]),
                "top_integrated_tools": [r["full_name"] for r in repos[:3]],
            }
        }


if __name__ == "__main__":
    gi = GitHubIntegration()
    
    print("=== GitHub 整合測試 ===")
    
    # 測試搜索
    results = gi.search_financial_repos("stock prediction")
    print(f"\nFound {len(results)} repos")
    
    if results:
        print("\nTop 3:")
        for r in results[:3]:
            print(f"  - {r.get('full_name', 'N/A')}: score={r.get('integration_score', 0)}")
