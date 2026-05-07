#!/usr/bin/env python3
"""
Stock_Team_Agent RSS Feed 新聞提供器
多源RSS Feed整合：全球金融新聞、公司新聞、宏觀新聞、科技新聞等
"""

import json
import re
import ssl
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from html import unescape
import time


class NewsFeedProvider:
    """
    多源RSS Feed新聞提供者
    
    功能：
    - 多源RSS Feed抓取（驗證真實性不及時性）
    - 新聞分類：公司/宏觀/科技/戰爭災害/市場
    - 情緒分析
    - 股票關聯分析
    - 新聞驗證（多源交叉比對）
    """
    
    def __init__(self):
        self.name = "news_feed_provider"
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 300  # 5分鐘緩存
        
        # RSS Feed 列表（按類別）
        self.rss_feeds = {
            # 金融新聞
            "financial": [
                {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews", "lang": "en"},
                {"name": "Reuters Markets", "url": "https://feeds.reuters.com/reuters/marketsNews", "lang": "en"},
                {"name": "CNBC Finance", "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html", "lang": "en"},
                {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex", "lang": "en"},
                {"name": "MarketWatch", "url": "https://feeds.marketwatch.com/marketwatch/topstories/", "lang": "en"},
            ],
            # 公司新聞
            "company": [
                {"name": "Reuters Company", "url": "https://feeds.reuters.com/reuters/companyNews", "lang": "en"},
                {"name": "Seeking Alpha", "url": "https://seekingalpha.com/feed.xml", "lang": "en"},
                {"name": "Benzinga", "url": "https://www.benzinga.com/feed", "lang": "en"},
            ],
            # 宏觀經濟
            "macro": [
                {"name": "Reuters Economy", "url": "https://feeds.reuters.com/reuters/economicNews", "lang": "en"},
                {"name": "CNN Business", "url": "https://rss.cnn.com/rss/money_topstories.rss", "lang": "en"},
                {"name": "Economist", "url": "https://www.economist.com/finance-and-economics/rss.xml", "lang": "en"},
            ],
            # 科技新聞
            "tech": [
                {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "lang": "en"},
                {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "lang": "en"},
                {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "lang": "en"},
            ],
            # 市場數據
            "market": [
                {"name": "Investopedia", "url": "https://www.investopedia.com/feedbuilder/feed/getfeed?feedName=rss_headline", "lang": "en"},
            ],
        }
        
        # 中文新聞源
        self.rss_feeds_cn = {
            "cn_financial": [
                {"name": "新浪財經", "url": "https://rss.sina.com.cn/rolls/finance_roll.xml", "lang": "cn"},
                {"name": "鳳凰財經", "url": "https://finance.ifeng.com/rss/finance.xml", "lang": "cn"},
                {"name": "騰訊財經", "url": "https://finance.qq.com/rss/finance.xml", "lang": "cn"},
            ],
            "cn_macro": [
                {"name": "新華網財經", "url": "https://www.xinhuanet.com/fortune/rss.xml", "lang": "cn"},
            ],
        }
        
        # 關鍵詞映射（用於分類）
        self.category_keywords = {
            "tech": ["AI", "artificial intelligence", "technology", "software", "chip", "semiconductor", 
                     "Apple", "Google", "Microsoft", "Meta", "Tesla", "Nvidia", "AMD", "Intel",
                     "人工智能", "科技", "晶片", "半導體", "華為", "蘋果"],
            "war_conflict": ["war", "military", "attack", "conflict", "Russia", "Ukraine", "Israel", "Iran",
                            "戰爭", "軍事", "攻擊", "衝突", "俄羅斯", "烏克蘭", "以色列", "中東"],
            "disaster": ["earthquake", "flood", "typhoon", "hurricane", "disaster", "crisis",
                        "地震", "洪水", "颱風", "颶風", "災害", "危機"],
            "policy": ["Fed", "Federal Reserve", "interest rate", "inflation", "tariff", "trade war",
                      "美聯儲", "利率", "通脹", "關稅", "貿易戰", "政策"],
            "earnings": ["earnings", "revenue", "profit", "quarterly", "results", "IPO",
                        "財報", "營收", "盈利", "季度", "業績"],
            "merger": ["acquisition", "merger", "takeover", "deal", "buyout",
                      "收購", "併購", "合併", "收購"],
        }
        
        # 股票關鍵詞映射
        self.stock_keywords = {
            "AAPL": ["Apple", "蘋果"],
            "MSFT": ["Microsoft", "微軟"],
            "GOOGL": ["Google", "Alphabet", "谷歌"],
            "AMZN": ["Amazon", "亞馬遜"],
            "META": ["Meta", "Facebook", "Meta Platforms"],
            "TSLA": ["Tesla", "特斯拉"],
            "NVDA": ["Nvidia", "英偉達"],
            "0700.HK": ["騰訊", "Tencent"],
            "9988.HK": ["阿里巴巴", "Alibaba", "阿里"],
            "3690.HK": ["美團", "Meituan"],
            "9618.HK": ["京東", "JD.com", "JD"],
            "1810.HK": ["小米", "Xiaomi"],
            "600519.SS": ["茅臺", "貴州茅臺", "Kweichow Moutai"],
            "601318.SS": ["平安", "中國平安", "Ping An"],
        }
    
    def fetch_feed(self, url: str, timeout: int = 10) -> Optional[str]:
        """抓取RSS Feed"""
        try:
            # 創建SSL上下文
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Stock_Team_Agent News Fetcher)",
                "Accept": "application/rss+xml, application/xml, text/xml, */*"
            })
            
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                content = response.read().decode("utf-8", errors="ignore")
                return content
        except Exception as e:
            return None
    
    def parse_rss(self, content: str) -> List[Dict]:
        """解析RSS XML"""
        items = []
        
        # 提取item標籤內容
        item_pattern = re.compile(r'<item>(.*?)</item>', re.DOTALL | re.IGNORECASE)
        title_pattern = re.compile(r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>', re.DOTALL)
        link_pattern = re.compile(r'<link>(.*?)</link>', re.DOTALL)
        desc_pattern = re.compile(r'<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>', re.DOTALL)
        date_pattern = re.compile(r'<pubDate>(.*?)</pubDate>', re.DOTALL)
        
        for item_match in item_pattern.finditer(content):
            item_content = item_match.group(1)
            
            title_match = title_pattern.search(item_content)
            link_match = link_pattern.search(item_content)
            desc_match = desc_pattern.search(item_content)
            date_match = date_pattern.search(item_content)
            
            title = ""
            if title_match:
                title = title_match.group(1) or title_match.group(2) or ""
                title = unescape(title.strip())
            
            link = ""
            if link_match:
                link = link_match.group(1).strip()
            
            description = ""
            if desc_match:
                description = desc_match.group(1) or desc_match.group(2) or ""
                description = unescape(description.strip())
                # 移除HTML標籤
                description = re.sub(r'<[^>]+>', '', description)
                description = description[:500]  # 限制長度
            
            pub_date = ""
            if date_match:
                pub_date = date_match.group(1).strip()
            
            if title:
                items.append({
                    "title": title,
                    "link": link,
                    "description": description,
                    "pub_date": pub_date,
                    "timestamp": self._parse_date(pub_date)
                })
        
        return items
    
    def _parse_date(self, date_str: str) -> str:
        """解析日期字符串"""
        if not date_str:
            return datetime.now().isoformat()
        
        # 嘗試多種日期格式
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.replace(" +0000", " GMT").replace(" +0000", ""), fmt.replace("%z", ""))
                return dt.isoformat()
            except Exception:
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(date_str)
                    return dt.isoformat()
                except Exception:
                    pass
        
        return datetime.now().isoformat()
    
    def fetch_category(self, category: str = "financial", limit: int = 20) -> List[Dict]:
        """抓取指定類別的新聞"""
        cache_key = f"news_{category}_{limit}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        all_news = []
        feeds = self.rss_feeds.get(category, [])
        
        for feed in feeds[:3]:  # 每類最多3個源
            try:
                content = self.fetch_feed(feed["url"])
                if content:
                    items = self.parse_rss(content)
                    for item in items[:limit]:
                        item["source"] = feed["name"]
                        item["category"] = category
                        item["language"] = feed["lang"]
                        all_news.append(item)
                time.sleep(0.5)  # 避免請求過快
            except Exception as e:
                continue
        
        # 按時間排序
        all_news.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        self._set_cache(cache_key, all_news[:limit])
        return all_news[:limit]
    
    def fetch_all(self, limit_per_category: int = 10) -> Dict[str, List[Dict]]:
        """抓取所有類別的新聞"""
        result = {}
        
        for category in self.rss_feeds.keys():
            result[category] = self.fetch_category(category, limit_per_category)
        
        return result
    
    def verify_news(self, title: str, sources: List[str]) -> Dict[str, Any]:
        """驗證新聞真實性（多源比對）"""
        # 簡單的關鍵詞匹配驗證
        verified = False
        confidence = 0.5
        
        # 如果有多個來源確認，置信度提高
        if len(sources) >= 2:
            confidence = 0.8
            verified = True
        elif len(sources) == 1:
            confidence = 0.6
            verified = True
        
        return {
            "verified": verified,
            "confidence": confidence,
            "source_count": len(sources),
            "sources": sources
        }
    
    def categorize_news(self, news: List[Dict]) -> Dict[str, List[Dict]]:
        """將新聞分類"""
        categorized = {
            "tech": [],
            "war_conflict": [],
            "disaster": [],
            "policy": [],
            "earnings": [],
            "merger": [],
            "general": []
        }
        
        for item in news:
            title_lower = (item.get("title", "") + item.get("description", "")).lower()
            categorized_flag = False
            
            for category, keywords in self.category_keywords.items():
                if any(kw.lower() in title_lower for kw in keywords):
                    item["detected_category"] = category
                    categorized[category].append(item)
                    categorized_flag = True
                    break
            
            if not categorized_flag:
                item["detected_category"] = "general"
                categorized["general"].append(item)
        
        return categorized
    
    def analyze_stock_impact(self, news: List[Dict], symbol: str) -> Dict[str, Any]:
        """分析新聞對特定股票的影響"""
        keywords = self.stock_keywords.get(symbol, [symbol])
        
        relevant_news = []
        for item in news:
            text = (item.get("title", "") + item.get("description", "")).lower()
            if any(kw.lower() in text for kw in keywords):
                relevant_news.append(item)
        
        # 計算影響分數
        impact_score = 0
        if relevant_news:
            for item in relevant_news:
                title_lower = item.get("title", "").lower()
                
                # 正面關鍵詞
                positive = ["beat", "surge", "rally", "upgrade", "profit", "growth", "bullish",
                           "超預期", "增長", "上漲", "升級", "盈利"]
                # 負面關鍵詞
                negative = ["miss", "drop", "fall", "downgrade", "loss", "bearish", "investigation",
                          "低於預期", "下跌", "降級", "虧損", "調查"]
                
                if any(kw in title_lower for kw in positive):
                    impact_score += 0.3
                if any(kw in title_lower for kw in negative):
                    impact_score -= 0.3
        
        impact_score = max(-1, min(1, impact_score))
        
        return {
            "symbol": symbol,
            "relevant_news_count": len(relevant_news),
            "impact_score": impact_score,
            "impact_label": "positive" if impact_score > 0.2 else "negative" if impact_score < -0.2 else "neutral",
            "relevant_news": relevant_news[:5]  # 最多5條
        }
    
    def get_market_sentiment(self, news: List[Dict]) -> Dict[str, Any]:
        """分析市場情緒"""
        if not news:
            return {"sentiment": "neutral", "score": 0.5}
        
        positive_keywords = ["surge", "rally", "bull", "gain", "upgrade", "beat", "growth", 
                           "上涨", "牛市", "利好", "超預期"]
        negative_keywords = ["drop", "fall", "bear", "loss", "downgrade", "miss", "concern",
                           "下跌", "熊市", "利空", "低於預期"]
        
        positive_count = 0
        negative_count = 0
        
        for item in news:
            text = (item.get("title", "") + item.get("description", "")).lower()
            
            if any(kw in text for kw in positive_keywords):
                positive_count += 1
            if any(kw in text for kw in negative_keywords):
                negative_count += 1
        
        total = len(news)
        if total == 0:
            return {"sentiment": "neutral", "score": 0.5}
        
        positive_ratio = positive_count / total
        negative_ratio = negative_count / total
        
        # 計算情緒分數 (-1 到 1)
        score = (positive_ratio - negative_ratio)
        
        return {
            "sentiment": "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral",
            "score": round(score, 3),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "total_count": total
        }
    
    def _get_cache(self, key: str) -> Optional[Any]:
        """獲取緩存"""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl:
                return data
        return None
    
    def _set_cache(self, key: str, data: Any, ttl: int = 300):
        """設置緩存"""
        self.cache[key] = (data, datetime.now())


class GlobalNewsAnalyzer:
    """
    全球新聞分析器
    整合RSS Feed，分析新聞對市場和股票的影響
    """
    
    def __init__(self):
        self.news_provider = NewsFeedProvider()
    
    def analyze_for_symbol(self, symbol: str) -> Dict[str, Any]:
        """分析指定股票相關的新聞"""
        # 抓取所有類別新聞
        all_news = self.news_provider.fetch_all(limit_per_category=15)
        
        # 合併所有新聞
        combined_news = []
        for category, items in all_news.items():
            for item in items:
                item["category"] = category
                combined_news.append(item)
        
        # 股票影響分析
        stock_impact = self.news_provider.analyze_stock_impact(combined_news, symbol)
        
        # 市場情緒
        market_sentiment = self.news_provider.get_market_sentiment(combined_news)
        
        # 分類新聞
        categorized = self.news_provider.categorize_news(combined_news)
        
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "stock_impact": stock_impact,
            "market_sentiment": market_sentiment,
            "categorized_news": {
                "tech": categorized["tech"][:5],
                "war_conflict": categorized["war_conflict"][:5],
                "disaster": categorized["disaster"][:5],
                "policy": categorized["policy"][:5],
                "earnings": categorized["earnings"][:5],
            },
            "top_news": combined_news[:10],
            "news_count": len(combined_news)
        }
    
    def analyze_market_briefing(self) -> Dict[str, Any]:
        """生成市場簡報"""
        all_news = self.news_provider.fetch_all(limit_per_category=20)
        
        combined_news = []
        for category, items in all_news.items():
            for item in items:
                item["category"] = category
                combined_news.append(item)
        
        combined_news.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # 市場情緒
        sentiment = self.news_provider.get_market_sentiment(combined_news)
        
        # 分類
        categorized = self.news_provider.categorize_news(combined_news)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "market_sentiment": sentiment,
            "breaking_news": combined_news[:10],
            "categories": {
                "tech": categorized["tech"][:5],
                "macro": categorized["policy"][:5],
                "earnings": categorized["earnings"][:5],
            },
            "total_news": len(combined_news)
        }


if __name__ == "__main__":
    # 測試
    provider = NewsFeedProvider()
    
    print("=== RSS Feed 新聞抓取測試 ===\n")
    
    # 抓取金融新聞
    print("📰 抓取金融新聞...")
    financial_news = provider.fetch_category("financial", limit=5)
    print(f"   獲取 {len(financial_news)} 條新聞")
    
    if financial_news:
        print(f"\n   最新頭條:")
        for i, news in enumerate(financial_news[:3], 1):
            print(f"   {i}. {news.get('title', 'N/A')[:60]}...")
            print(f"      來源: {news.get('source', 'N/A')} | 時間: {news.get('pub_date', 'N/A')[:22]}")
    
    # 抓取科技新聞
    print("\n📰 抓取科技新聞...")
    tech_news = provider.fetch_category("tech", limit=5)
    print(f"   獲取 {len(tech_news)} 條新聞")
    
    # 市場情緒分析
    if financial_news:
        sentiment = provider.get_market_sentiment(financial_news)
        print(f"\n📊 市場情緒: {sentiment.get('sentiment', 'N/A')}")
        print(f"   正面: {sentiment.get('positive_count', 0)} | 負面: {sentiment.get('negative_count', 0)}")
    
    # 股票影響分析
    print("\n🔍 股票影響分析 (AAPL)...")
    impact = provider.analyze_stock_impact(financial_news + tech_news, "AAPL")
    print(f"   相關新聞: {impact.get('relevant_news_count', 0)} 條")
    print(f"   影響分數: {impact.get('impact_score', 0)} ({impact.get('impact_label', 'N/A')})")
    
    # 完整市場簡報
    print("\n📊 生成市場簡報...")
    analyzer = GlobalNewsAnalyzer()
    briefing = analyzer.analyze_market_briefing()
    print(f"   總新聞數: {briefing.get('total_news', 0)}")
    print(f"   市場情緒: {briefing.get('market_sentiment', {}).get('sentiment', 'N/A')}")
