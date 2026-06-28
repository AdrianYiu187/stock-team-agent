"""
社交情緒資料提供者 (Social Sentiment Provider)
===============================================
功能：
1. 抓取 Google News RSS（英文 + 中文）— 替換已封鎖的 Reddit/PTT
2. 抓取 Finnhub News（備用，需 API Key）
3. 生成情緒分數（bullish/bearish/neutral）

作者：Hermes Agent
日期：2026-05-11（v2 — 移除 Reddit/PTT，替換為 Google News RSS）
"""

import requests
import re
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
from datetime import datetime

# ============================================================================
# 常數設定
# ============================================================================

GOOGLE_NEWS_RSS_EN = "https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en&num=20"
GOOGLE_NEWS_RSS_ZH = "https://news.google.com/rss/search?q={ticker}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&num=20"
# v5.10: Finnhub API 已停用（fetch_finnhub_news 0 caller），刪除未使用常數

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
# Google News RSS 情緒分析函數
# ============================================================================

def _parse_rss_items(xml_text: str, source: str) -> List[Dict[str, Any]]:
    """解析 Google News RSS XML，回傳標題列表"""
    items = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            if title:
                items.append({
                    "title": title,
                    "link": link,
                    "pub_date": pub_date,
                    "source": source
                })
    except ET.ParseError as e:
        print(f"⚠️ RSS 解析錯誤 ({source}): {e}")
    return items


def fetch_google_news_sentiment(ticker: str) -> Dict[str, Any]:
    """
    抓取 Google News RSS 搜尋結果的情緒
    同時抓英文（全球）和中文（台/港）的新聞

    Args:
        ticker: 股票代碼（例如：TSLA, 2330, 0700）

    Returns:
        包含新聞情緒分析的字典
    """
    ticker = ticker.upper()
    result = {
        "source": "google_news",
        "ticker": ticker,
        "timestamp": datetime.now().isoformat(),
        "posts": [],
        "aggregated_sentiment": "neutral",
        "sentiment_score": 0,
        "total_posts": 0,
        "error": None
    }

    all_items = []

    # 英文新聞（全球）
    en_url = GOOGLE_NEWS_RSS_EN.format(ticker=ticker)
    try:
        resp = requests.get(en_url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        items = _parse_rss_items(resp.text, "google_news_en")
        all_items.extend(items)
        print(f"   📰 Google News EN: 抓到 {len(items)} 條新聞")
    except Exception as e:
        print(f"   ⚠️ Google News EN 失敗: {e}")

    time.sleep(0.3)

    # 中文新聞（台/港）
    zh_url = GOOGLE_NEWS_RSS_ZH.format(ticker=ticker)
    try:
        resp = requests.get(zh_url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        items = _parse_rss_items(resp.text, "google_news_zh")
        all_items.extend(items)
        print(f"   📰 Google News ZH: 抓到 {len(items)} 條新聞")
    except Exception as e:
        print(f"   ⚠️ Google News ZH 失敗: {e}")

    # 情緒分析
    sentiment_scores = []
    for item in all_items:
        text = item["title"]
        si = _calculate_sentiment_score(text)
        item["sentiment"] = si["sentiment"]
        item["sentiment_score"] = si["score"]
        item["bullish"] = si["bullish"]
        item["bearish"] = si["bearish"]
        sentiment_scores.append(si["score"])

    result["posts"] = all_items
    result["total_posts"] = len(all_items)

    if sentiment_scores:
        avg = sum(sentiment_scores) / len(sentiment_scores)
        result["sentiment_score"] = int(avg)
        if avg > 10:
            result["aggregated_sentiment"] = "bullish"
        elif avg < -10:
            result["aggregated_sentiment"] = "bearish"
        else:
            result["aggregated_sentiment"] = "neutral"

    return result


# ============================================================================
# 綜合社交情緒分析函數
# ============================================================================

def get_combined_social_sentiment(ticker: str, finnhub_token: str = "") -> Dict[str, Any]:
    """
    合併 Google News RSS 和 Finnhub 的情緒分析結果
    
    Args:
        ticker: 股票代碼
        finnhub_token: Finnhub API Key（可選）
    
    Returns:
        包含綜合情緒分析的字典
        {
            "ticker": "TSLA",
            "timestamp": "...",
            "google_news": {...},
            "finnhub": {...},
            "combined_sentiment": "bullish/bearish/neutral",
            "combined_score": -100 到 100,
            "data_available": True/False,
            "sources": ["google_news"],
            "summary": "文字摘要"
        }
    """
    ticker = ticker.upper()

    # Google News（主資料源，v5.10: Finnhub 已移除）
    google_data = fetch_google_news_sentiment(ticker)
    finnhub_data = {"total_posts": 0, "sentiment_score": 0}  # v5.10 stub

    # 計算合併分數
    sources_used = []
    total_score = 0
    total_weight = 0

    if google_data["total_posts"] > 0:
        sources_used.append("google_news")
        weight = google_data["total_posts"]
        total_score += google_data["sentiment_score"] * weight
        total_weight += weight

    combined_score = int(total_score / total_weight) if total_weight > 0 else 0
    combined_sentiment = "bullish" if combined_score > 10 else "bearish" if combined_score < -10 else "neutral"

    total_posts = google_data["total_posts"] + finnhub_data.get("total_posts", 0)

    if total_posts > 0:
        summary = (
            f"{ticker} 在新聞中共有 {total_posts} 篇相關報導。"
            f"整體情緒偏向 {combined_sentiment}（分數：{combined_score}）。"
            f"資料來源：{', '.join(sources_used) if sources_used else '無'}。"
        )
    else:
        summary = f"無法取得 {ticker} 的新聞資料。"

    return {
        "ticker": ticker,
        "timestamp": datetime.now().isoformat(),
        "google_news": google_data,
        "finnhub": finnhub_data,
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
    print("社交情緒資料提供者測試 (v2 — Google News RSS)")
    print("=" * 60)
    
    # 測試 Google News 情緒抓取
    print("\n📊 測試 Google News 情緒抓取 (TSLA)...")
    news_result = fetch_google_news_sentiment("TSLA")
    print(f"   總文章數: {news_result['total_posts']}")
    print(f"   情緒判定: {news_result['aggregated_sentiment']}")
    print(f"   情緒分數: {news_result['sentiment_score']}")
    
    # 測試中文新聞
    print("\n📊 測試中文新聞 (2330)...")
    news_zh = fetch_google_news_sentiment("2330")
    print(f"   總文章數: {news_zh['total_posts']}")
    print(f"   情緒判定: {news_zh['aggregated_sentiment']}")
    print(f"   情緒分數: {news_zh['sentiment_score']}")
    
    # 測試 Finnhub News（需要 token）
    print("\n📊 測試 Finnhub News (AAPL, 需要 API Key)...")
    finnhub_result = fetch_finnhub_news("AAPL", "")
    print(f"   總文章數: {finnhub_result['total_posts']}")
    print(f"   錯誤: {finnhub_result.get('error', 'None')}")
    
    # 測試綜合情緒分析
    print("\n📊 測試綜合情緒分析 (TSLA)...")
    combined = get_combined_social_sentiment("TSLA")
    print(f"   合併情緒: {combined['combined_sentiment']}")
    print(f"   合併分數: {combined['combined_score']}")
    print(f"   資料可用: {combined['data_available']}")
    print(f"   摘要: {combined['summary']}")
    
    print("\n" + "=" * 60)
    print("測試完成")
    print("=" * 60)
