"""
社交情緒資料提供者 (Social Sentiment Provider)
===============================================
功能：
1. 抓取 Reddit (r/wallstreetbets, r/stocks, r/investing) 帖子標題和評分
2. 抓取 PTT Stock 板（使用批踢煮 Web API）
3. 生成情緒分數（bullish/bearish/neutral）

作者：Hermes Agent
日期：2026-05-11
"""

import requests
import re
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

# ============================================================================
# 常數設定
# ============================================================================

REDDIT_SUBREDDITS = ["wallstreetbets", "stocks", "investing"]
REDDIT_API_BASE = "https://www.reddit.com"
PTT_API_BASE = "https://api.ptt.cc/v1"
PTT_BOARD = "Stock"

# 情緒關鍵詞字典（用於簡單的情緒分析）
BULLISH_KEYWORDS = [
    "moon", "to the moon", "bullish", "long", "buy", "calls", "queeze",
    "rocket", "hold", "gain", "profit", "up", "high", "breakout", "rally",
    "surge", "jump", "soar", "all time high", "ATH", "green", "winner",
    "tendies", "diamond hands", "bull", "long position"
]

BEARISH_KEYWORDS = [
    "put", "bearish", "short", "sell", "drop", "crash", "dump", "lose",
    "loss", "down", "red", "bear", "wash", "cut", "trap", "fade",
    "breakdown", "orrection", "plunge", "tumble", "sold", "puts", "liquidate"
]

# 請求逾時設定（秒）
REQUEST_TIMEOUT = 10


# ============================================================================
# 輔助函數
# ============================================================================

def _calculate_sentiment_score(text: str) -> Dict[str, Any]:
    """
    計算文字的情緒分數
    
    Args:
        text: 要分析的文字（已轉小寫）
    
    Returns:
        包含分數和情緒判定的字典
    """
    text_lower = text.lower()
    
    bullish_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text_lower)
    bearish_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text_lower)
    
    total = bullish_count + bearish_count
    
    if total == 0:
        return {"score": 0, "sentiment": "neutral", "bullish": 0, "bearish": 0}
    
    # 分數範圍：-100 到 +100
    score = int(((bullish_count - bearish_count) / total) * 100)
    
    if score > 20:
        sentiment = "bullish"
    elif score < -20:
        sentiment = "bearish"
    else:
        sentiment = "neutral"
    
    return {
        "score": score,
        "sentiment": sentiment,
        "bullish": bullish_count,
        "bearish": bearish_count
    }


def _fetch_with_fallback(url: str, headers: Optional[Dict] = None, 
                         params: Optional[Dict] = None) -> Optional[Dict]:
    """
    帶有回退機制的 HTTP GET 請求
    
    Args:
        url: 目標 URL
        headers: 請求頭
        params: URL 參數
    
    Returns:
        JSON 回應資料，或失敗時返回 None
    """
    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"⚠️ 請求失敗: {url} - 錯誤: {str(e)}")
        return None


# ============================================================================
# Reddit 情緒分析函數
# ============================================================================

def fetch_reddit_sentiment(ticker: str) -> Dict[str, Any]:
    """
    抓取 Reddit 上與指定股票代碼相關的帖子情緒
    
    Args:
        ticker: 股票代碼（例如：AAPL, TSLA）
    
    Returns:
        包含 Reddit 情緒分析的字典
        {
            "source": "reddit",
            "ticker": "TSLA",
            "timestamp": "2026-05-11T...",
            "posts": [...],
            "aggregated_sentiment": "bullish/bearish/neutral",
            "sentiment_score": 0-100,
            "total_posts": N,
            "error": None 或錯誤訊息
        }
    """
    ticker = ticker.upper()
    result = {
        "source": "reddit",
        "ticker": ticker,
        "timestamp": datetime.now().isoformat(),
        "posts": [],
        "aggregated_sentiment": "neutral",
        "sentiment_score": 0,
        "total_posts": 0,
        "error": None
    }
    
    all_posts = []
    
    # 遍歷每個 subreddit
    for subreddit in REDDIT_SUBREDDITS:
        try:
            # 使用 reddit.com.json API（無需認證）
            url = f"{REDDIT_API_BASE}/r/{subreddit}/search.json"
            params = {
                "q": ticker,
                "restrict_sr": 1,
                "sort": "relevance",
                "limit": 25,  # 每次最多取 25 篇
                "t": "month"   # 過去一個月
            }
            
            data = _fetch_with_fallback(url, params=params)
            
            if data and "data" in data:
                children = data["data"].get("children", [])
                
                for post in children:
                    post_data = post.get("data", {})
                    
                    # 提取標題和評分
                    title = post_data.get("title", "")
                    score = post_data.get("score", 0)
                    num_comments = post_data.get("num_comments", 0)
                    created_utc = post_data.get("created_utc", 0)
                    
                    if title:
                        sentiment_info = _calculate_sentiment_score(title)
                        
                        all_posts.append({
                            "subreddit": subreddit,
                            "title": title,
                            "score": score,
                            "num_comments": num_comments,
                            "created_utc": created_utc,
                            "sentiment": sentiment_info["sentiment"],
                            "sentiment_score": sentiment_info["score"],
                            "bullish_matches": sentiment_info["bullish"],
                            "bearish_matches": sentiment_info["bearish"]
                        })
            
            # 避免請求過快
            time.sleep(0.5)
            
        except Exception as e:
            print(f"⚠️ 抓取 r/{subreddit} 時發生錯誤: {str(e)}")
            continue
    
    # 計算總體情緒
    result["posts"] = all_posts
    result["total_posts"] = len(all_posts)
    
    if all_posts:
        # 使用加權平均（評分作為權重）計算整體情緒
        total_weight = sum(p["score"] for p in all_posts if p["score"] > 0)
        
        if total_weight > 0:
            weighted_score = sum(
                p["sentiment_score"] * p["score"] 
                for p in all_posts 
                if p["score"] > 0
            ) / total_weight
            
            result["sentiment_score"] = int(weighted_score)
            
            if weighted_score > 10:
                result["aggregated_sentiment"] = "bullish"
            elif weighted_score < -10:
                result["aggregated_sentiment"] = "bearish"
            else:
                result["aggregated_sentiment"] = "neutral"
        else:
            # 如果沒有評分，使用簡單平均
            avg_score = sum(p["sentiment_score"] for p in all_posts) / len(all_posts)
            result["sentiment_score"] = int(avg_score)
            result["aggregated_sentiment"] = "neutral"
    
    return result


# ============================================================================
# PTT 情緒分析函數
# ============================================================================

def fetch_ptt_sentiment(ticker: str) -> Dict[str, Any]:
    """
    抓取 PTT Stock 板上與指定股票代碼相關的文章情緒
    
    Args:
        ticker: 股票代碼（例如：2330, 0050）
    
    Returns:
        包含 PTT 情緒分析的字典
        {
            "source": "ptt",
            "ticker": "2330",
            "timestamp": "2026-05-11T...",
            "posts": [...],
            "aggregated_sentiment": "bullish/bearish/neutral",
            "sentiment_score": 0-100,
            "total_posts": N,
            "error": None 或錯誤訊息
        }
    """
    ticker = ticker.upper()
    result = {
        "source": "ptt",
        "ticker": ticker,
        "timestamp": datetime.now().isoformat(),
        "posts": [],
        "aggregated_sentiment": "neutral",
        "sentiment_score": 0,
        "total_posts": 0,
        "error": None
    }
    
    try:
        # 使用 PTT Web API 抓取 Stock 板文章列表
        # 先取得文章列表
        board_url = f"{PTT_API_BASE}/board/{PTT_BOARD}/articles"
        
        articles_data = _fetch_with_fallback(board_url)
        
        if not articles_data:
            # 如果 API 失敗，返回空數據（不阻斷主流程）
            result["error"] = "無法連線到 PTT API"
            return result
        
        all_posts = []
        articles = articles_data.get("data", [])
        
        for article in articles:
            article_id = article.get("aid", "")
            title = article.get("title", "")
            
            # 檢查標題是否包含股票代碼
            # 支援多种格式：$2330、2330、TSLA 等
            if not title:
                continue
            
            # 簡單關鍵字匹配（不區分大小寫）
            if ticker.lower() not in title.lower():
                # 也檢查一般股票代碼格式（如 $2330）
                if f"${ticker}" not in title and f"#{ticker}" not in title:
                    continue
            
            # 抓取文章詳情
            detail_url = f"{PTT_API_BASE}/article/{article_id}"
            detail_data = _fetch_with_fallback(detail_url)
            
            if detail_data:
                content = detail_data.get("data", {}).get("content", "")
                push_count = detail_data.get("data", {}).get("push_count", 0)
                created_at = detail_data.get("data", {}).get("created_at", "")
                
                # 合併標題和內容進行情緒分析
                full_text = f"{title} {content}"
                sentiment_info = _calculate_sentiment_score(full_text)
                
                all_posts.append({
                    "article_id": article_id,
                    "title": title,
                    "push_count": push_count,
                    "created_at": created_at,
                    "sentiment": sentiment_info["sentiment"],
                    "sentiment_score": sentiment_info["score"],
                    "bullish_matches": sentiment_info["bullish"],
                    "bearish_matches": sentiment_info["bearish"]
                })
            
            # 避免請求過快
            time.sleep(0.3)
            
            # 限制處理的文章數量
            if len(all_posts) >= 20:
                break
        
        result["posts"] = all_posts
        result["total_posts"] = len(all_posts)
        
        if all_posts:
            avg_score = sum(p["sentiment_score"] for p in all_posts) / len(all_posts)
            result["sentiment_score"] = int(avg_score)
            
            if avg_score > 10:
                result["aggregated_sentiment"] = "bullish"
            elif avg_score < -10:
                result["aggregated_sentiment"] = "bearish"
            else:
                result["aggregated_sentiment"] = "neutral"
                
    except Exception as e:
        result["error"] = f"PTT 抓取錯誤: {str(e)}"
        print(f"⚠️ 抓取 PTT 時發生錯誤: {str(e)}")
    
    return result


# ============================================================================
# 綜合社交情緒分析函數
# ============================================================================

def get_combined_social_sentiment(ticker: str) -> Dict[str, Any]:
    """
    合併 Reddit 和 PTT 的情緒分析結果
    
    Args:
        ticker: 股票代碼
    
    Returns:
        包含綜合情緒分析的字典
        {
            "ticker": "TSLA",
            "timestamp": "2026-05-11T...",
            "reddit": {...},
            "ptt": {...},
            "combined_sentiment": "bullish/bearish/neutral",
            "combined_score": -100 到 100,
            "data_available": True/False,
            "sources": ["reddit", "ptt"],
            "summary": "文字摘要"
        }
    """
    ticker = ticker.upper()
    
    # 分別抓取各來源資料
    reddit_data = fetch_reddit_sentiment(ticker)
    ptt_data = fetch_ptt_sentiment(ticker)
    
    # 計算合併分數
    sources_used = []
    total_score = 0
    total_weight = 0
    
    if reddit_data["total_posts"] > 0:
        sources_used.append("reddit")
        # 使用文章數量作為權重
        weight = reddit_data["total_posts"]
        total_score += reddit_data["sentiment_score"] * weight
        total_weight += weight
    
    if ptt_data["total_posts"] > 0:
        sources_used.append("ptt")
        weight = ptt_data["total_posts"]
        total_score += ptt_data["sentiment_score"] * weight
        total_weight += weight
    
    # 計算最終合併分數
    if total_weight > 0:
        combined_score = int(total_score / total_weight)
    else:
        combined_score = 0
    
    # 判定合併後的情緒
    if combined_score > 10:
        combined_sentiment = "bullish"
    elif combined_score < -10:
        combined_sentiment = "bearish"
    else:
        combined_sentiment = "neutral"
    
    # 計算總文章數
    total_posts = reddit_data["total_posts"] + ptt_data["total_posts"]
    
    # 生成摘要文字
    if total_posts > 0:
        summary = (
            f"{ticker} 在社交媒體上共蒐集到 {total_posts} 篇文章。"
            f"整體情緒偏向 {combined_sentiment}（分數：{combined_score}）。"
            f"資料來源：{', '.join(sources_used) if sources_used else '無'}。"
        )
    else:
        summary = f"無法取得 {ticker} 的社交媒體資料。"
    
    return {
        "ticker": ticker,
        "timestamp": datetime.now().isoformat(),
        "reddit": reddit_data,
        "ptt": ptt_data,
        "combined_sentiment": combined_sentiment,
        "combined_score": combined_score,
        "data_available": total_posts > 0,
        "sources": sources_used,
        "total_posts": total_posts,
        "summary": summary
    }


# ============================================================================
# 測試區塊
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("社交情緒資料提供者測試")
    print("=" * 60)
    
    # 測試 Reddit 情緒抓取
    print("\n📊 測試 Reddit 情緒抓取 (TSLA)...")
    reddit_result = fetch_reddit_sentiment("TSLA")
    print(f"   總文章數: {reddit_result['total_posts']}")
    print(f"   情緒判定: {reddit_result['aggregated_sentiment']}")
    print(f"   情緒分數: {reddit_result['sentiment_score']}")
    
    # 測試 PTT 情緒抓取
    print("\n📊 測試 PTT 情緒抓取 (2330)...")
    ptt_result = fetch_ptt_sentiment("2330")
    print(f"   總文章數: {ptt_result['total_posts']}")
    print(f"   情緒判定: {ptt_result['aggregated_sentiment']}")
    print(f"   情緒分數: {ptt_result['sentiment_score']}")
    
    # 測試綜合情緒分析
    print("\n📊 測試綜合情緒分析 (AAPL)...")
    combined = get_combined_social_sentiment("AAPL")
    print(f"   合併情緒: {combined['combined_sentiment']}")
    print(f"   合併分數: {combined['combined_score']}")
    print(f"   資料可用: {combined['data_available']}")
    print(f"   摘要: {combined['summary']}")
    
    print("\n" + "=" * 60)
    print("測試完成")
    print("=" * 60)
