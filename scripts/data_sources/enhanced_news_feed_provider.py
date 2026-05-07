#!/usr/bin/env python3
"""
Stock_Team_Agent 增強版新聞提供器 v2
- 根據實測結果，只保留真的能抓到的RSS源
- 實測成功的源: 東方日報(HK), 36kr(CN), Yahoo Finance(US)
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
from concurrent.futures import ThreadPoolExecutor, as_completed


class EnhancedNewsFeedProvider:
    """
    增強版新聞提供者 v2.1
    
    實測成功的RSS源:
    - [HK] 東方日報 - 18條/天
    - [CN] 36kr - 30條/天
    - [US] Yahoo Finance - 48條/天
    
    策略:
    1. 主抓這3個可靠源
    2. 擴展英文源的覆蓋範圍
    3. 技術指標自動補充情緒
    4. ⚠️ v2.1: 集成 MiniMax LLM 情緒分析
    """
    
    def __init__(self, use_llm: bool = False):
        self.name = "enhanced_news_feed_provider_v2.1"
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 300
        
        # MiniMax LLM 集成（預設關閉，避免75×14s掛起問題）
        self.use_llm = use_llm
        self._llm = None
        
        # ========== 實測成功的RSS源（只有這些靠譜）==========
        self.working_feeds = {
            "hk": [
                {"name": "東方日報", "url": "https://orientaldaily.on.cc/rss/finance.xml", "lang": "cn", "type": "hk_financial"},
            ],
            "cn": [
                {"name": "36kr", "url": "https://36kr.com/feed", "lang": "cn", "type": "cn_tech"},
            ],
            "us": [
                {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex", "lang": "en", "type": "financial"},
                {"name": "CNBC", "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html", "lang": "en", "type": "financial"},
                {"name": "MarketWatch", "url": "https://feeds.marketwatch.com/marketwatch/topstories/", "lang": "en", "type": "market"},
            ]
        }
        
        # 擴展英文科技源
        self.tech_feeds = {
            "tech_en": [
                {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "lang": "en", "type": "tech"},
                {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "lang": "en", "type": "tech"},
                {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "lang": "en", "type": "tech"},
            ]
        }
        
        # ========== 股票關鍵詞映射（擴展到更多港股）==========
        self.stock_keywords = {
            # 港股科技/手機
            "1810.HK": ["小米", "Xiaomi", "小米集團", "雷軍", "紫米"],
            "0700.HK": ["騰訊", "Tencent", "QQ", "微信"],
            "9988.HK": ["阿里巴巴", "Alibaba", "阿里", "淘寶"],
            "3690.HK": ["美團", "Meituan", "外賣", "點評"],
            "9618.HK": ["京東", "JD.com", "JD", "京東物流"],
            "2382.HK": ["舜宇光學", "Sunny Optical", "光學鏡頭"],
            "1929.HK": ["周大福", "Chow Tai Fook", "珠寶"],
            "2319.HK": ["蒙牛乳業", "Mengniu", "蒙牛"],
            "2202.HK": ["萬科", "Vanke", "房地產"],
            "2628.HK": ["中國人壽", "China Life", "保險"],
            "3968.HK": ["招商銀行", "CMB", "銀行"],
            "6030.HK": ["野村", "Nomura", "日資"],
            # A股
            "600519.SS": ["茅臺", "貴州茅臺", "Kweichow Moutai", "茅臺酒"],
            "300750.SZ": ["寧德時代", "CATL", "新能源汽車", "鋰電池"],
            "688981.SS": ["中芯國際", "SMIC", "半導體", "芯片"],
            "000333.SZ": ["美的集團", "Midea", "家電"],
            # 美股
            "AAPL": ["Apple", "蘋果", "iPhone", "Mac"],
            "TSLA": ["Tesla", "特斯拉", "馬斯克", "Elon Musk", "電動車"],
            "NVDA": ["Nvidia", "英偉達", "GPU", "AI晶片", "輝達"],
            "MSFT": ["Microsoft", "微軟", "Azure", "雲端"],
            "GOOGL": ["Google", "Alphabet", "谷歌", "AI"],
            "META": ["Meta", "Facebook", "臉書", "Instagram"],
        }
        
        # ========== 情緒關鍵詞（更全面）==========
        self.positive_keywords = [
            # 英文
            "surge", "rally", "bull", "gain", "upgrade", "beat", "growth", "soar", "jump", "rise",
            "record high", "breakthrough", "outperform", "strong buy", "exceed",
            # 中文
            "上漲", "增長", "超預期", "利好", "突破", "升級", "買入", "強勁", "創新高",
            "反弹", "回升", "看好", "增持", "推薦", "首選", "目標價", "業績靚",
            "大漲", "飙升", "暴漲", "收益", "盈利增加", "派息", "回購", "中標",
        ]
        
        self.negative_keywords = [
            # 英文
            "drop", "fall", "bear", "loss", "downgrade", "miss", "concern", "plunge", "crash",
            "investigation", "lawsuit", "fraud", "scandal", "bankruptcy",
            "cut", "reduce", "weak", "warn",
            # 中文
            "下跌", "暴跌", "虧損", "降級", "利空", "低於預期", "警示", "風險",
            "裁員", "倒閉", "破產", "調查", "訴訟", "醜聞", "造假", "虧本",
            "大跳水", "暴跌", "失血", "拋售", "沽售", "減持", "目標價下調", "預警",
        ]
    
    def fetch_feed(self, url: str, timeout: int = 10) -> Optional[str]:
        """抓取RSS Feed"""
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Stock News Fetcher v2)",
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
                description = re.sub(r'<[^>]+>', '', description)
                description = description[:300]
            
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
    
    def fetch_all_working(self, limit_per_source: int = 20) -> Dict[str, List[Dict]]:
        """抓取所有實測成功的RSS源（並行加速）"""
        cache_key = f"working_feeds_{limit_per_source}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        result: Dict[str, List[Dict]] = {}
        total_news: List[Dict] = []
        
        # 建構所有 feed 任務
        all_feeds_list = []
        for region, feeds in {**self.working_feeds, **self.tech_feeds}.items():
            for feed in feeds[:2]:  # 每源最多2個
                all_feeds_list.append((region, feed))
        
        def fetch_single(region: str, feed: Dict) -> Tuple[str, str, List[Dict]]:
            try:
                content = self.fetch_feed(feed["url"], timeout=8)
                if not content:
                    return region, feed["name"], []
                items = self.parse_rss(content)
                processed = []
                for item in items[:limit_per_source]:
                    item["source"] = feed["name"]
                    item["region"] = region
                    item["lang"] = feed["lang"]
                    item["type"] = feed.get("type", "general")
                    processed.append(item)
                return region, feed["name"], processed
            except Exception as e:
                import logging
                logging.warning(f"[EnhancedNewsFeed] fetch_single {feed['name']} failed: {e}")
                return region, feed["name"], []
        
        # 並行抓取（最多8個執行緒）
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(fetch_single, r, f): (r, f["name"]) for r, f in all_feeds_list}
            for future in as_completed(futures, timeout=30):
                try:
                    region, feed_name, items = future.result()
                    if region not in result:
                        result[region] = []
                    result[region].extend(items)
                    total_news.extend(items)
                except Exception as e:
                    import logging
                    logging.warning(f"[EnhancedNewsFeed] future result failed: {e}")
        
        # 按時間排序
        total_news.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        result["all"] = total_news
        self._set_cache(cache_key, result)
        return result
    
    def analyze_stock_impact(self, news: List[Dict], symbol: str) -> Dict[str, Any]:
        """分析新聞對特定股票的影響"""
        keywords = self.stock_keywords.get(symbol, [symbol])
        
        relevant_news = []
        for item in news:
            text = (item.get("title", "") + item.get("description", "")).lower()
            if any(kw.lower() in text for kw in keywords):
                relevant_news.append(item)
        
        impact_score = 0
        if relevant_news:
            for item in relevant_news:
                title = item.get("title", "").lower()
                desc = item.get("description", "").lower()
                full_text = title + " " + desc
                
                pos_count = sum(1 for kw in self.positive_keywords if kw.lower() in full_text)
                neg_count = sum(1 for kw in self.negative_keywords if kw.lower() in full_text)
                
                impact_score += (pos_count * 0.25) - (neg_count * 0.25)
        
        impact_score = max(-1, min(1, impact_score))
        
        return {
            "symbol": symbol,
            "relevant_news_count": len(relevant_news),
            "impact_score": round(impact_score, 3),
            "impact_label": "positive" if impact_score > 0.2 else "negative" if impact_score < -0.2 else "neutral",
            "relevant_news": relevant_news[:5]
        }
    
    def analyze_with_price_context(
        self,
        news: List[Dict],
        symbol: str,
        ytd_return: float = 0,
        momentum_20d: float = 0,
        volatility: float = 0
    ) -> Dict[str, Any]:
        """
        結合價格趨勢分析情緒 v2
        
        價格趨勢權重提升（60%）
        新聞情緒權重（40%）
        """
        # 1. 新聞情緒（帶超時保護，防止LLM調用掛起）
        news_impact = self.analyze_stock_impact(news, symbol)
        try:
            import signal
            def timeout_handler(signum, frame):
                raise TimeoutError("get_market_sentiment timed out")
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(5)  # 5秒超時
            try:
                news_sentiment = self.get_market_sentiment(news)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        except (TimeoutError, AttributeError):
            # Fallback: 簡單關鍵詞情緒
            pos_kw, neg_kw = ["利多", "利好", "漲", "買入", "超預期"], ["利空", "下跌", "虧損", "風險", "警告"]
            pos = sum(1 for it in news[:20] if any(k in (it.get("title","")+it.get("description","")) for k in pos_kw))
            neg = sum(1 for it in news[:20] if any(k in (it.get("title","")+it.get("description","")) for k in neg_kw))
            score = (pos - neg) / max(pos + neg, 1) * 0.5 + 0.5
            news_sentiment = {"sentiment": "positive" if score > 0.55 else "negative" if score < 0.45 else "neutral", "score": score}
        except Exception:
            news_sentiment = {"sentiment": "neutral", "score": 0.5}
        
        # 2. 價格趨勢情緒
        price_sentiment = 0.5
        
        if ytd_return < -30:
            price_sentiment = 0.20
        elif ytd_return < -20:
            price_sentiment = 0.30
        elif ytd_return < -10:
            price_sentiment = 0.40
        elif ytd_return < 0:
            price_sentiment = 0.45
        elif ytd_return < 10:
            price_sentiment = 0.55
        elif ytd_return < 20:
            price_sentiment = 0.65
        else:
            price_sentiment = 0.75
        
        # 動量調整
        if momentum_20d < -15:
            price_sentiment = max(0.1, price_sentiment - 0.25)
        elif momentum_20d < -5:
            price_sentiment = max(0.2, price_sentiment - 0.15)
        elif momentum_20d > 15:
            price_sentiment = min(0.9, price_sentiment + 0.25)
        elif momentum_20d > 5:
            price_sentiment = min(0.8, price_sentiment + 0.15)
        
        # 波動性調整（高波動 = 負面）
        if volatility > 40:
            price_sentiment = max(0.15, price_sentiment - 0.1)
        elif volatility > 25:
            price_sentiment = max(0.25, price_sentiment - 0.05)
        
        # 3. 加權計算綜合情緒
        news_weight = 0.40
        price_weight = 0.60
        
        news_score = news_sentiment.get("score", 0)
        price_score = price_sentiment - 0.5
        
        combined_score = (news_score * news_weight) + (price_score * price_weight)
        combined_score = max(-1, min(1, combined_score))
        
        # 4. 置信度
        news_count = news_impact.get("relevant_news_count", 0)
        if news_count >= 5 and abs(combined_score) > 0.3:
            confidence = "high"
        elif news_count >= 2:
            confidence = "medium"
        else:
            confidence = "low"
        
        return {
            "symbol": symbol,
            "news_sentiment": news_sentiment,
            "price_sentiment": price_sentiment,
            "price_momentum": momentum_20d,
            "ytd_return": ytd_return,
            "volatility": volatility,
            "combined_score": round(combined_score, 3),
            "combined_label": "positive" if combined_score > 0.2 else "negative" if combined_score < -0.2 else "neutral",
            "news_count": news_count,
            "confidence": confidence
        }
    
    def _get_cache(self, key: str) -> Optional[Any]:
        if key in self.cache:
            data, timestamp = self.cache[key]
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl:
                return data
        return None
    
    def _set_cache(self, key: str, data: Any, ttl: int = 300):
        self.cache[key] = (data, datetime.now())
    
    @property
    def llm(self):
        """延遲加載 MiniMax LLM 實例"""
        if self._llm is None and self.use_llm:
            try:
                import sys
                sys.path.insert(0, str(__file__).rsplit("/", 1)[0])
                from integrations.minimax_llm import MiniMaxLLM
                self._llm = MiniMaxLLM()
                # 測試是否可用
                if not self._llm.enabled:
                    self._llm = None
            except Exception as e:
                import logging
                logging.warning(f"[EnhancedNewsFeed] LLM init failed: {e}")
                self._llm = None
        return self._llm
    
    def analyze_sentiment_llm(self, text: str) -> Dict[str, Any]:
        """
        使用 MiniMax LLM 分析情緒（增強版）
        
        返回:
            {
                "sentiment": "positive|negative|neutral",
                "score": float,
                "confidence": float,
                "reasoning": str,
                "⚠️ LLM_USED": True  # 標記使用LLM
            }
        """
        if not self.llm:
            # Fallback 到關鍵詞
            return self._keyword_sentiment(text)
        
        result = self.llm.analyze_sentiment(text)
        result["⚠️ LLM_USED"] = True
        return result
    
    def _keyword_sentiment(self, text: str) -> Dict[str, Any]:
        """關鍵詞情緒分析（當LLM不可用時的回退）"""
        positive_keywords = [
            "surge", "rally", "bull", "gain", "upgrade", "beat", "growth", "soar", "jump", "rise",
            "上漲", "增長", "超預期", "利好", "突破", "升級", "買入", "強勁", "創新高",
            "反弹", "回升", "看好", "增持", "推薦", "首選", "目標價", "業績靚",
            "大漲", "飙升", "暴漲", "收益", "盈利增加", "派息", "回購", "中標",
        ]
        negative_keywords = [
            "drop", "fall", "bear", "loss", "downgrade", "miss", "concern", "plunge", "crash",
            "investigation", "lawsuit", "fraud", "scandal", "bankruptcy",
            "下跌", "暴跌", "虧損", "降級", "利空", "低於預期", "警示", "風險",
            "裁員", "倒閉", "破產", "調查", "訴訟", "醜聞", "造假", "虧本",
            "大跳水", "暴跌", "失血", "拋售", "沽售", "減持", "目標價下調", "預警",
        ]
        
        text_lower = text.lower()
        pos_count = sum(1 for kw in positive_keywords if kw.lower() in text_lower)
        neg_count = sum(1 for kw in negative_keywords if kw.lower() in text_lower)
        
        score = (pos_count - neg_count) / max(pos_count + neg_count, 1)
        
        return {
            "sentiment": "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral",
            "score": score,
            "confidence": 0.3,  # 關鍵詞置信度較低
            "reasoning": "關鍵詞回退機制（MiniMax LLM不可用）",
            "⚠️ FALLBACK_KEYWORD": True
        }
    
    def get_market_sentiment(self, news: List[Dict]) -> Dict[str, Any]:
        """分析市場情緒（關鍵詞版本：快速穩定，避免LLM API掛起）"""
        if not news:
            return {"sentiment": "neutral", "score": 0.5, "⚠️ NO_NEWS": True}
        
        # 限制處理的news數量避免API掛起
        news_subset = news[:20]
        sentiments = []
        for item in news_subset:
            text = item.get("title", "") + " " + item.get("description", "")
            result = self._keyword_sentiment(text)
            sentiments.append(result)
        
        # 聚合
        total_score = sum(s.get("score", 0) for s in sentiments)
        avg_score = total_score / len(sentiments) if sentiments else 0
        
        positive_count = sum(1 for s in sentiments if s.get("sentiment") == "positive")
        negative_count = sum(1 for s in sentiments if s.get("sentiment") == "negative")
        total = len(sentiments)
        
        # 標記是否使用LLM
        llm_used = any(s.get("⚠️ LLM_USED") for s in sentiments)
        
        return {
            "sentiment": "positive" if avg_score > 0.2 else "negative" if avg_score < -0.2 else "neutral",
            "score": round(avg_score, 3),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "total_count": total,
            "⚠️ LLM_USED": llm_used,
            "⚠️ FALLBACK_KEYWORD": not llm_used
        }
    
    def analyze_stock_impact_llm(self, news: List[Dict], symbol: str) -> Dict[str, Any]:
        """
        使用 LLM 分析新聞對特定股票的影響（增強版）
        """
        if not self.llm:
            return self.analyze_stock_impact(news, symbol)
        
        # 找出相關新聞
        keywords = self.stock_keywords.get(symbol, [symbol])
        relevant_news = []
        for item in news:
            text = (item.get("title", "") + item.get("description", "")).lower()
            if any(kw.lower() in text for kw in keywords):
                relevant_news.append(item)
        
        if not relevant_news:
            return {
                "symbol": symbol,
                "relevant_news_count": 0,
                "impact_score": 0,
                "impact_label": "neutral",
                "⚠️ LLM_USED": True,
                "reasoning": "無相關新聞"
            }
        
        # 使用LLM分析每條新聞
        impact_scores = []
        for item in relevant_news[:5]:
            title = item.get("title", "")
            desc = item.get("description", "")
            result = self.llm.analyze_stock_news(title, desc, symbol)
            if "impact_score" in result:
                impact_scores.append(result["impact_score"])
        
        avg_impact = sum(impact_scores) / len(impact_scores) if impact_scores else 0
        
        return {
            "symbol": symbol,
            "relevant_news_count": len(relevant_news),
            "impact_score": round(avg_impact, 3),
            "impact_label": "positive" if avg_impact > 0.2 else "negative" if avg_impact < -0.2 else "neutral",
            "relevant_news": relevant_news[:5],
            "⚠️ LLM_USED": True
        }


def main():
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"=== 增強版新聞提供器 v2 測試 ===\n")
    
    provider = EnhancedNewsFeedProvider()
    
    # 抓取所有工作源
    all_feeds = provider.fetch_all_working(limit_per_source=20)
    
    print(f"RSS來源: {list(all_feeds.keys())}")
    total = len(all_feeds.get("all", []))
    print(f"總新聞數: {total}")
    print()
    
    # 按區域統計
    for region in ["hk", "cn", "us"]:
        if region in all_feeds:
            print(f"  [{region.upper()}] {len(all_feeds[region])} 條")
    
    # 測試情緒分析
    combined = all_feeds.get("all", [])
    result = provider.analyze_with_price_context(
        combined,
        symbol,
        ytd_return=0.0,
        momentum_20d=0.0,
        volatility=20.0
    )
    
    print(f"\n=== {symbol} 情緒分析 ===")
    print(f"新聞情緒: {result['news_sentiment']['sentiment']} ({result['news_sentiment']['score']:.2f})")
    print(f"  正面: {result['news_sentiment']['positive_count']}, 負面: {result['news_sentiment']['negative_count']}")
    print(f"價格情緒: {result['price_sentiment']:.2f}")
    print(f"YTD: {result['ytd_return']:.2f}%, 動量: {result['price_momentum']:.2f}%, 波動性: {result['volatility']:.1f}%")
    print(f"綜合情緒: {result['combined_label']} ({result['combined_score']:.2f})")
    print(f"置信度: {result['confidence']}")

if __name__ == "__main__":
    main()