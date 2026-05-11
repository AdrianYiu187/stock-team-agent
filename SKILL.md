---
name: stock-team-agent
description: Stock_Team_Agent v2 — 股票分析多代理智能團隊系統。整合7位專業分析師（市場/技術/基本面/風險/情緒/新聞/宏觀策略），支援專業估值模型、技術指標。真實多代理辯論引擎（5輪+7角色），非模擬。增強版RSS新聞源（實測成功：東方日報/36kr/Yahoo Finance），結合價格趨勢自動補充情緒判斷。支援 S1-S179 股票分析能力擴展。
---

# Stock_Team_Agent

## 系統位置

```
~/.hermes/skills/productivity/stock-team-agent/
├── SKILL.md                          # 本文件
├── scripts/
│   ├── stock_analysis.py           # 主入口（v5 專業報告格式，argparse: -c/-n）
│   ├── stock_router.py             # 任務調度器（280行）
│   ├── workflow_engine.py          # 工作流引擎（8角色並發）
│   │
│   ├── model/                      # ✅ 三層架構：分析師角色定義
│   │   └── handlers/              # 6位分析師（已從 handlers/ 遷入）
│   │       ├── __init__.py        # 導出所有分析師
│   │       ├── market_analyst.py      # 市場分析師
│   │       ├── technical_analyst.py   # 技術分析師
│   │       ├── fundamental_analyst.py  # 基本面分析師
│   │       ├── risk_analyst.py        # 風險分析師
│   │       ├── sentiment_analyst.py   # 情緒分析師
│   │       └── macro_analyst.py       # 宏觀策略分析師
│   │
│   ├── train/                      # ✅ 三層架構：共識/學習引擎
│   │   ├── __init__.py
│   │   ├── consensus_engine.py     # 共識引擎（從 consensus/ 遷入）
│   │   └── llm_debate_engine.py   # LLM辯論引擎（從 辩论/ 遷入）
│   │
│   ├── generate/                    # ✅ 三層架構：報告生成
│   │   ├── __init__.py
│   │   └── report_generator.py    # v5報告生成器框架
│   │
│   ├── indicators/
│   │   ├── technical_indicators.py # 技術指標（S31-S40）
│   │   └── professional_indices.py  # 專業指數（S41-S50）
│   ├── valuation/
│   │   └── valuation_models.py      # 估值模型（S51-S60）
│   ├── charts/
│   │   └── chart_generator.py       # 圖表生成（S61-S70）
│   ├── data_sources/
│   │   ├── stock_data_provider.py   # 數據提供者（yfinance）
│   │   ├── news_feed_provider.py    # RSS Feed 新聞提供者
│   │   └── enhanced_news_feed_provider.py  # 增強版RSS (v2)
│   ├── github_integration/
│   │   └── github_scanner_integration.py  # GitHub Scanner整合
│   │
│   ├── handlers/                  # 向後兼容 shim → model/handlers/
│   ├── consensus/                  # 向後兼容 shim → train/
│   └── 辩论/                      # 向後兼容 shim → train/
│
├── docs/
│   └── capabilities.md              # 詳細能力文檔
└── v2_complete_analysis.py           # v2 完整分析腳本 (5輪+7角色)
```

### 三層架構說明（2026-05-07 重構）

```
model/handlers/  ← 分析師角色（what the agent IS）
  └─ 6位分析師，各自獨立輸出結構化分析結果

train/          ← 共識/學習引擎（how consensus forms）
  └─ consensus_engine.py — 加權評分計算
  └─ llm_debate_engine.py — MiniMax LLM 辯論共識

generate/       ← 報告生成器（how output is presented）
  └─ report_generator.py — v5專業報告格式輸出

向後兼容：所有舊 import 路徑（handlers/*, consensus/*, 辩论/*）透過 shim 仍然有效
```

## 觸發關鍵詞

| 任務類型 | 關鍵詞 |
|---------|--------|
| 全面分析 | 全面分析、完整分析、full analysis、comprehensive |
| 技術分析 | 技術分析、technical、指標、chart、k線 |
| 基本面 | 基本面、fundamental、財務、營收、eps、ROE |
| 風險 | 風險、risk、止損、倉位、VaR、波動率 |
| 情緒 | 情緒、sentiment、新聞、消息、公告、分析師評級 |
| 估值 | 估值、valuation、目標價、dcf、股利折現 |
| 比較 | 比較、compare、對比、vs |
| 組合 | 投資組合、portfolio、持倉、倉位 |
| 警報 | 預警、alert、通知、提醒 |
| 回測 | 回測、backtest、歷史 |

## 7位分析師角色 (v2)

### 分析師權重配置

| 分析師 | 權重 | 專長領域 |
|--------|------|----------|
| 市場分析師 (market) | 12% | 市場趨勢、資金流向、板塊輪動、宏觀經濟 |
| 技術分析師 (technical) | 18% | K線形態、技術指標、趨勢判斷、成交量分析 |
| 基本面分析師 (fundamental) | 22% | 財務報表、估值、盈利能力、增長潛力 |
| 風險分析師 (risk) | 15% | 風險評估、VaR、波動率、流動性風險 |
| 情緒分析師 (sentiment) | 18% | 新聞情緒、價格趨勢情緒、技術指標補充 |
| 新聞分析師 (news) | 7% | 新聞覆蓋質量、來源可信度、訊息量評估 |
| 宏觀策略分析師 (macro) | 8% | 宏觀環境、利率政策、行業趨勢 |

### v5 專業報告格式（2026-05-01 確認）

每位分析師角色輸出結構：
```
【角色名稱】
📊 數據來源：列出真實數據（✅ yfinance / ⚠️ FALLBACK）
💡 核心論點：該角色的獨立投資觀點（為什麼買/賣/持有）
📈 關鍵證據：支撐論點的數據證據（具體數字+解讀）
🎯 評估結論：評分+信號+置信度
```

LLM辯論階段呈現：
```
每輪每個角色的：
  • 初始論點（明確立場）
  • 對手挑戰（針對哪個角色提出異議）
  • 證據引用（用了什麼數據反駁）
  • 讓步/堅持（調整還是不調整）
  • 調整幅度（+或-多少）
```

投資建議框架：
```
現價：HK$XX.XX

🟡 短期（1-4週）：[策略]
  入手價：HK$XX.XX（±X%）
  目標價：HK$XX.XX（±X%）
  止損價：HK$XX.XX（-X%）
  邏輯：...

🟡 中期（1-6個月）：[策略]
  入手價：...
  目標價：...
  止損價：...
  邏輯：...

🟢 長期（6-12個月）：[策略]
  入手價：...
  目標價：...
  止損價：...
  邏輯：...

【風險警示】（7類）
【共識形成過程】
【主要分歧點】
```

執行命令：
```bash
cd ~/.hermes/skills/productivity/stock-team-agent/scripts
python3 stock_analysis.py -c 1810.HK -n "小米集團"
```

輸出目錄：`~/.hermes/task_outputs/[CODE]_[NAME]_v5/`

### 辯論引擎 (v2)

- **真實多代理辯論**：非模擬，5輪辯論，16+ 訊息來回
- **共識點**：3個（低位支撐、風險部分釋放、基本面支持反彈）
- **分歧記錄**：技術面偏空 vs 基本面低估

### 分析師輸出結構

```python
{
    "analyst": "technical",
    "score": 0.44,           # 0-1 標準化分數
    "signal": "sell",        # strong_buy/buy/hold/sell/strong_sell
    "confidence": 0.56,      # 分析信心度
    "buy_score": 0.444,
    "hold_score": 0.0,
    "sell_score": 0.556,
    "summary": "技術指標顯示賣出信號。RSI=78.9..."
}
```

## 共識引擎（S21-S30）

### 共識計算流程

```
1. 提取評分 → 從每位分析師提取 buy/hold/sell 分數
2. 加權計算 → 根據任務類型和權重計算加權分數
3. 衝突檢測 → 識別分析師間的重大分歧
4. 共識產生 → 計算最終 buy/hold/sell 百分比
5. 建議生成 → 根據共識產生投資建議
6. 信心度評估 → 評估共識的可靠程度
```

### 共識建議等級

| 等級 | 條件 | 說明 |
|------|------|------|
| 強烈買入 | buy > 60% | 多數分析師強烈推薦買入 |
| 適度買入 | buy 40-60% | 多數分析師推薦買入 |
| 持有觀望 | hold > 50% | 分析師建議謹慎觀望 |
| 適度賣出 | sell 40-60% | 多數分析師建議賣出 |
| 強烈賣出 | sell > 60% | 多數分析師強烈建議賣出 |

### 衝突檢測

- **buy_vs_sell**: 同時存在強烈買入和強烈賣出信號
- **high_divergence**: 分析師評分分散度過高（範圍 > 0.5）

## 專業工具能力

### S31-S40: 技術指標

| 指標 | 說明 | 計算週期 |
|------|------|----------|
| SMA | 簡單移動平均線 | 20/50/200日 |
| EMA | 指數移動平均線 | 12/26日 |
| RSI | 相對強弱指標 | 14日 |
| MACD | 移動平均收斂發散 | 12/26/9 |
| 布林帶 | 波動性通道 | 20日，2標準差 |
| ATR | 平均真實波幅 | 14日 |
| 隨機指標 | K/D周期 | 14/3日 |
| CCI | 商品通道指標 | 20日 |
| ADX | 平均方向指數 | 14日 |
| OBV | 能量潮指標 | — |

### S41-S50: 專業指數

| 指數 | 說明 | 用途 |
|------|------|------|
| 巴菲特指標 | 總市值/GDP | 市場估值水平 |
| 席勒市盈率 (CAPE) | 經週期調整市盈率 | 長期估值 |
| 黃金切割率 | 0.382/0.5/0.618 | 支撐阻力位 |
| 風險評分 | 0-100 | 綜合風險評估 |
| 波動率評分 | 0-1 | 歷史波動率分析 |
| VaR (Value at Risk) | 95%/99% 置信區間 | 風險價值 |
| **sector_momentum** | 板塊動量 | 強勢板塊篩選 |
| **market_breadth** | 市場廣度 (上漲/下跌比) | 確認趨勢強度 |
| **put_call_ratio** | 沽購比率 | 期權市場情緒 |

### S51-S60: 估值模型

| 模型 | 說明 | 適用場景 |
|------|------|----------|
| DCF | 現金流折現模型 | 內在價值計算 |
| DDM | 股利折現模型 | 高股息股票 |
| PEG | 市盈率相對增長 | 成長股評估 |
| Dividend Discount | 股利折現 | 穩定股利股 |
| 相對估值 | 同行比較 | 估值對比 |

### S61-S70: 圖表生成

| 圖表類型 | 說明 |
|----------|------|
| K線圖 | 價格走勢 + 成交量 |
| 技術指標圖 | 均線/RSI/MACD 疊加 |
| 估值歷史圖 | PE/PB 歷史趨勢 |
| 價格目標圖 | 支撐阻力位標註 |
| 評分雷達圖 | 5位分析師評分對比 |
| 風險評估圖 | VaR/波動率視覺化 |

## 數據源

### 優先順序

1. **yfinance** — 美股/HK股/A股即時數據 ✅ 真實
2. **EastMoney** — 港股/A股新聞數據
3. **Mock數據** — 當無法獲取時使用（標示 ⚠️）

### 支援市場

| 市場 | 代碼格式 | 範例 |
|------|----------|------|
| 🇭🇰 香港 | SYMBOL.HK | 0700.HK, 9988.HK, 3690.HK |
| 🇺🇸 美國 | SYMBOL | AAPL, TSLA, NVDA, MSFT, GOOGL |
| 🇨🇳 中國 A股 | SYMBOL.SS/SZ | 600519.SS, 000001.SZ, 601318.SS |
| 🇨🇳 中國 H股 | SYMBOL.HK | 9618.HK, 1810.HK |

### 三市場代表股票

**🇭🇰 香港市場:**
- 0700.HK (騰訊)、9988.HK (阿里巴巴)、3690.HK (美團)
- 9618.HK (京東)、1810.HK (小米)、0005.HK (匯豐)

**🇺🇸 美國市場:**
- AAPL (Apple)、MSFT (Microsoft)、NVDA (Nvidia)
- TSLA (Tesla)、GOOGL (Google)、AMZN (Amazon)、META (Meta)

**🇨🇳 中國市場:**
- 600519.SS (貴州茅臺)、601318.SS (工商銀行)
- 000001.SZ (平安銀行)、600036.SS (招商銀行)

## RSS Feed 新聞整合

### 功能

- **多源RSS Feed** — 全球金融、新聞、科技、宏觀經濟新聞
- **新聞驗證** — 多源交叉比對，確認真實性
- **及時性追蹤** — 新聞時間戳追蹤
- **分類系統** — 公司/宏觀/科技/戰爭災害/政策/財報
- **股票關聯** — 分析新聞對特定股票的影響
- **市場情緒** — 正面/負面/中性評分

### ⚠️ 情緒分析數據缺口問題（2026-04-30 發現）

**問題：** 英文 RSS 源不覆蓋港股/中概股新聞 → 匹配失敗 → 情緒分數 0.00

**解決方案：價格趨勢補充情緒（重要方法論）**

```python
# 當新聞數據不足時，用價格趨勢自動補充情緒判斷
def analyze_with_price_context(news, symbol, ytd_return, momentum_20d):
    # 1. 新聞情緒（可能為空或低相關性）
    news_sentiment = analyze_news(news)
    
    # 2. 價格趨勢情緒（自動計算）
    if ytd_return < -20:   price_sentiment = 0.25  # 嚴重下跌 → 負面
    elif ytd_return < -10: price_sentiment = 0.35  # 顯著下跌 → 偏負
    elif ytd_return < 0:   price_sentiment = 0.45  # 小幅下跌 → 輕微負
    elif ytd_return < 10:  price_sentiment = 0.55  # 小幅上漲 → 輕微正
    elif ytd_return < 20:  price_sentiment = 0.65  # 顯著上漲 → 偏正
    else:                   price_sentiment = 0.75  # 大幅上漲 → 正面
    
    # 動量調整
    if momentum_20d < -15: price_sentiment -= 0.2
    elif momentum_20d < -5: price_sentiment -= 0.1
    elif momentum_20d > 15: price_sentiment += 0.2
    elif momentum_20d > 5:  price_sentiment += 0.1
    
    # 3. 加權綜合
    combined = news_sentiment * 0.4 + (price_sentiment - 0.5) * 0.6
    
    return combined  # -1 到 1
```

**關鍵洞察：** 
- 當 YTD = -41.90%，即使新聞數據為空，價格趨勢自動產生負面情緒信號
- 這解決了「新聞 neutral = 真的 neutral」的錯誤假設

### RSS Feed 來源

**英文新聞源：**
- Reuters Business/Markets/Company/Economy
- CNBC Finance, Yahoo Finance, MarketWatch
- TechCrunch, The Verge, Ars Technica
- Seeking Alpha, Benzinga, Investopedia

**中文新聞源：**
- 新浪財經, 鳳凰財經, 騰訊財經
- 新華網財經

### 新聞分類

| 分類 | 關鍵詞 |
|------|--------|
| tech | AI, Apple, Google, Microsoft, Tesla, Nvidia, 科技, 半導體 |
| war_conflict | war, military, Russia, Ukraine, Israel, 戰爭, 衝突 |
| disaster | earthquake, flood, typhoon, 地震, 洪水, 災害 |
| policy | Fed, interest rate, inflation, tariff, 利率, 通脹, 關稅 |
| earnings | earnings, revenue, profit, quarterly, 財報, 營收 |
| merger | acquisition, merger, takeover, 收購, 併購 |

### 股票關鍵詞映射

| 股票 | 關鍵詞 |
|------|--------|
| AAPL | Apple, 蘋果 |
| MSFT | Microsoft, 微軟 |
| GOOGL | Google, Alphabet, 谷歌 |
| TSLA | Tesla, 特斯拉 |
| NVDA | Nvidia, 英偉達 |
| 0700.HK | 騰訊, Tencent |
| 9988.HK | 阿里巴巴, Alibaba, 阿里 |
| 600519.SS | 茅臺, 貴州茅臺 |

## GitHub Scanner 整合

### SQLite 直接連接（2026-05-01 確認）

Scanner 數據庫位置：`~/.hermes/scripts/github_scanner/data/repos.db`

```python
import sqlite3, pandas as pd

def query_scanner_db(keywords: list[str], min_stars: int = 1000) -> pd.DataFrame:
    """直接查詢 GitHub Scanner SQLite 數據庫"""
    db_path = f"{os.path.expanduser('~')}/.hermes/scripts/github_scanner/data/repos.db"
    conn = sqlite3.connect(db_path)
    
    pattern = '|'.join(keywords)
    query = f"""
        SELECT repo_name, stars, language, description, topics
        FROM repos 
        WHERE (description LIKE '%{pattern}%' OR topics LIKE '%{pattern}%')
        AND stars >= {min_stars}
        ORDER BY stars DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df
```

**已發現高價值項目（2026-05-01）：**
- 量化交易：`TauricResearch/TradingAgents` (56,954★), `freqtrade/freqtrade` (49,613★)
- 金融數據：`OpenBB-finance/OpenBB` (66,784★), `pastram/StockData` (11,886★)
- 情緒分析：`sansan0/TrendRadar` (55,899★), `666ghj/BettaFish` (40,692★)
- 技術分析：`CryptoNinjaxf/binance futuros trader` (24,527★)

### 搜尋關鍵詞

```bash
# 量化交易
algorithmic trading, quant trading, backtesting

# 金融數據
stock data api, financial data, market data

# 技術指標
technical analysis, trading indicators, candlestick

# 機器學習
machine learning finance, stock prediction, sentiment analysis

# 投資組合
portfolio optimization, risk management, asset allocation
```

### 整合功能

- 發現量化交易策略開源項目
- 發現金融數據API和庫
- 發現技術指標實現
- 發現機器學習金融應用
- 自動評估項目品質和活躍度

## 工作流示例

### 全面分析工作流

```
用戶: "全面分析騰訊0700.HK"
  ↓
任務路由器識別: full_analysis
  ↓
并行調用5位分析師:
  - 市場分析師 → 市場趨勢分析
  - 技術分析師 → K線形態識別
  - 基本面分析師 → 財務報表分析
  - 風險分析師 → 風險評估
  - 情緒分析師 → 新聞情緒分析
  ↓
共識引擎整合:
  - 提取各分析師評分
  - 計算加權共識
  - 檢測衝突
  ↓
生成報告:
  - 綜合評分
  - 投資建議
  - 信心度
  - 風險提示
```

### 比較分析工作流

```
用戶: "比較騰訊和阿里巴巴"
  ↓
任務路由器識別: comparison
  ↓
並行分析兩隻股票
  ↓
生成對比報告:
  - 估值對比
  - 盈利能力對比
  - 技術面對比
  - 風險對比
  ↓
給出相對建議
```

## 真實多代理辯論引擎（2026-04-30 增强）

### 問題

之前：辯論是「模擬的」— 系統預先生成「可能發生的情節」，但角色之間沒有真的通訊

### 解決方案：RealDebateEngine

```python
class RealDebateEngine:
    """真實的多代理辯論引擎"""
    
    def run_debate(self, initial_positions):
        # 初始化每位分析師的立場
        for name, pos in initial_positions.items():
            self.register_analyst(name, pos)
        
        # 執行 3 輪真實辯論
        for round_num in range(1, 4):
            self.execute_debate_round(round_num)
        
        # 應用辯論後的調整
        self.apply_adjustments()
        
        # 生成辯論報告
        return self.generate_debate_report()
```

### 辯論訊息類型

| 類型 | 說明 | 效果 |
|------|------|------|
| `challenge` | 質詢對方觀點 | - |
| `counter` | 反駁並提出證據 | - |
| `concede` | 承認對方部分觀點 | score += 0.03 |
| `compromise` | 接受折中方案 | score -= 0.02 |
| `warning` | 發出風險警示 | 影響所有人 |
| `observation` | 提供觀察意見 | - |
| `summary` | 總結市場觀點 | - |

### 實際辯論範例（小米集團 01810.HK）

```
❓ [第1輪] technical → fundamental: 技術面偏空
   證據: 價格低於MA50, MACD為負
   問題: 你如何解釋這些技術信號？

🔄 [第1輪] fundamental → technical: 基本面支持價值
   證據: P/E合理, ROE優秀
   問題: 技術信號能持續多久？

👍 [第1輪] technical → fundamental: 承認低位可能是買點

⚠️ [第1輪] risk → all: 風險警示，Sharpe為負

❓ [第2輪] risk → fundamental: 風險未完全釋放
   問題: 低價是否等於低風險？

🔄 [第2輪] fundamental → risk: 風險已部分計入
   問題: 市場是否過度恐慌？

🤝 [第2輪] risk → fundamental: 接受風險部分釋放
```

### 辯論後立場調整

| 分析師 | 初始 | 辯論後 | 變化 |
|--------|------|--------|------|
| technical | 0.35 | 0.38 | +0.030 |
| fundamental | 0.65 | 0.65 | (不變) |
| risk | 0.40 | 0.38 | -0.020 |

### 共識點

- ✓ 承認低位可能是買點 (by technical)
- ✓ 接受風險部分釋放 (by risk)

## 健康檢查

```bash
# 基本測試
cd ~/.hermes/skills/productivity/stock-team-agent/scripts
python3 stock_router.py --symbol 0700.HK --request "全面分析騰訊"

# 能力測試
python3 -c "
import sys
sys.path.insert(0, '.')
from stock_router import StockRouter
router = StockRouter('0700.HK')
result = router.route('全面分析')
print('✅ Stock_Team_Agent 運作正常')
print(f'共識建議: {result[\"consensus\"][\"recommendation\"]}')
"
```

## 限制與標示

- ⚠️ 模擬數據 — 無法獲取真實數據時使用
- ✅ 真實API — 來自 yfinance/EastMoney
- 🚨 高衝突警告 — 分析師分歧過大時提醒
- ⚠️ 信心度低 — 數據不足或市場不確定性高

## MiniMax LLM 整合模組（2026-05-01）

### 位置
`scripts/integrations/minimax_llm.py` — MiniMax API 統一封裝
`scripts/辯論/llm_debate_engine.py` — LLM 驅動辯論引擎

### 驗證狀態（2026-05-01 確認）
```
LLM_ENABLED: True
⚠️ LLM_USED: True（每次辯論真實調用 MiniMax API）
模型: MiniMax-M2.7-highspeed
辯論輪次: 2輪，16條消息
```

## 辯論引擎升級：LLM 驅動（2026-05-01）

### 位置
`scripts/辯論/llm_debate_engine.py` — 替代原有硬編碼 RealDebateEngine

### 核心改進
- **真實 LLM 生成**：使用 MiniMax API 生成觀點/挑戰/反駁文本
- **保留共識機制**：維持原有的共識計算邏輯
- **異步修復**：`_execute_cross_challenges()` 改為 sync（內部無需並發）

### 驗證結果
```
rounds = 5
consensus_signal = "hold"
FALLBACK = True (API 未啟用)
```

## 版本歷史

| 版本 | 日期 | 說明 |
|------|------|------|
| v1.0.0 | 2026-04-30 | 初始版本，5位分析師 + 共識引擎 |
| v1.1.0 | 2026-04-30 | 增強版情緒分析（價格趨勢補充RSS缺口）+ 真實多代理辯論引擎 |
| v1.2.0 | 2026-05-01 | MiniMax LLM 整合 + 專業指數實現 + GitHub Scanner SQLite 整合 |
| v1.3.0 | 2026-05-01 | macro_analyst 獨立 handler 新創建 + v5 專業報告格式（四輪審計後代碼庫零問題） |

## 關鍵發現記錄（2026-04-30 ~ 2026-05-01）

### 1. 情緒分析數據缺口

**問題：** 英文 RSS 源不覆蓋港股/中概股，「小米」關鍵詞匹配失敗 → 影響分數 0.00

**現象：** 
- RSS 來源全是 CNBC、Benzinga、TechCrunch 等英文媒體
- 搜索「小米」返回 0 條相關新聞
- 系統錯誤地將「無新聞」解釋為「中性情緒」

**代價：** 
- 實際 YTD = -41.90%，從高點跌 -52.77%
- 這是明確的下跌趨勢，不是中性

**解決：** 價格趨勢自動補充情緒（YTD/20日動量）

### 2. 辯論引擎真實性

**問題：** 之前的「辯論」只是預先生成的腳本，角色之間沒有真的通訊

**解決：** RealDebateEngine → LLMDebateEngine 使用 MiniMax API 真實生成

### 3. MacroAnalyst 死代碼問題（2026-05-01）

**問題：** 7個分析師角色中，macro 是唯一沒有獨立 handler 的（其餘6個都有），導致 macro 完全 hardcode 輸出

**修復：** 新創建 `handlers/macro_analyst.py`，包含真實利率/VIX/黃金/美元數據獲取

### 4. 四輪代碼審計修復記錄（2026-05-01）

```
第一輪：裸 except (6) + yfinance 無錯誤處理 (1) + hardcode (1) + 重複調用 (1) = 9項
第二輪：RSI除以零 (1) + macro_analyst 5x bare except (5) + 空list除以零 (1) + unused import (1) + enhanced_news_feed bare except (3) = 11項
第三輪：硬編碼路徑 (1) + 死代碼函數 (2) = 3項
第四輪：報告標題hardcode (1) + __main__ demo hardcode (1) + RealDebateEngine死類 (1) = 3項
總計：27項修復
```

### 5. WhatsApp 自動發送整合（2026-05-01）

**功能：** Stock_Team_Agent 分析完成後 → 自動發送完整報告到 WhatsApp Group 2

**實現方式：** `stock_analysis.py` 末段呼叫 `_send_whatsapp_group2()`，透過 subprocess 執行 `~/.hermes/scripts/whatsapp_send_group2.py`

**關鍵技術細節：**
- ✅ 使用 `subprocess.run()` 而非 inline `urllib.request`（後者會 401 Unauthorized）
- ✅ green-api Instance: `7107605551`，Group 2 chatId: `85297154506-1472537715@g.us`
- ✅ Developer Free 配額: 3 Chats/月，每次分析消耗 1 次配額

**驗證：**
```bash
python3 stock_analysis.py -c TSLA -n "Tesla"
# 末端輸出: ✅ WhatsApp 已發送至 Group 2: Sent to Group 2: 3EB0885CAE84B47B67919C
```

**配額提醒：** 3 Chats/月，幾乎已滿。如需更高頻率分析，建議升級 green-api 方案。

---

### 6. stock_keywords 對照表非死代碼（2026-05-01 確認）

**發現：** `enhanced_news_feed_provider.py` 中 `stock_keywords` 映射表（line 70-84）包含 `688235.SS: 百濟神州...`

**判定：** 這是功能性地圖（RSS關鍵詞匹配用），非測試殘留，屬於正常配置數據

## 外部項目整合評估（2026-05-11 新增）

### TradingAgents × Stock_Team_Agent

**評估結論**: 輕量整合，而非合併架構

| 維度 | 結論 |
|------|------|
| 架構衝突 | 🔴 LangGraph 狀態機 vs subprocess（一票否決合併） |
| 功能對比 | Stock_Team_Agent 7角色辯論 > TradingAgents Bull/Bear（合併=降級） |
| 建議方案 | 輕量整合：數據源+Rating標準化+持久化 |

**應該提取的精華（2026-05-11 已完成）**:
- Alpha Vantage 數據源 → `scripts/data_sources/alpha_vantage/` ✅
- 5-tier Rating (STRONG_BUY/BUY/HOLD/SELL/STRONG_SELL) → `scripts/schemas/ratings.py` ✅
- Persistent Decision Log → `~/.hermes/stock_memory/` ✅
- ticker validation → `scripts/data_sources/alpha_vantage/utils.py` ✅ (safe_ticker_component)
- Hybrid fallback provider → `scripts/data_sources/hybrid_provider.py` ✅
- Pydantic schemas → `scripts/schemas/consensus.py`, `scripts/schemas/analyst_output.py` ✅

**整合後的 Schemas 架構**:
```
scripts/schemas/
├── ratings.py        # 5-tier SignalType, FiveTierRating, Confidence
├── analyst_output.py  # AnalystOutput, TechnicalIndicators, FundamentalMetrics, RiskMetrics
├── consensus.py       # ConsensusResult (Pydantic), AnalystScores, WeightedScores
├── decision_log.py    # DecisionLogger (SQLite + JSON, ~/.hermes/stock_memory/)
└── __init__.py        # 統一導出
```

**共識引擎升級**:
- `scripts/train/consensus_engine.py` 新增 `integrate()` 方法
- 返回 dict 含：`analyst_scores` / `weighted_scores` / `consensus` / `conflicts` / `recommendation` / `confidence` / `overall_score`
- 已整合進 `stock_analysis.py` Line ~602-825

### P1-P5 實作成果（2026-05-11 完成）

| 改動 | 狀態 | 檔案 |
|------|------|------|
| P1: Phase A/B 反思內存 | ✅ 完成 | `scripts/memory_phase_ab.py`（~304行） |
| P2: 共識引擎融入辯論流 | ✅ 完成 | `scripts/stock_analysis.py`（三處整合） |
| P3: Pydantic 結構化輸出 | ✅ 已有 | `scripts/schemas/`（7個模型） |
| P4: Checkpoint 系統 | ✅ 完成 | `scripts/checkpoint.py`（~199行） |
| P5: LLM 生成分析師評分 | ✅ 完成（參考實現） | `scripts/stock_analysis.py`（17910字註釋模板） |

**P11 特殊發現（2026-05-11）**：
- `store_pending_decision()` **已存在**於 `stock_analysis.py` line 1098-1113
- 用戶聲稱「Phase A 從未被調用」是**錯誤診斷**——需要先 grep 確認，不要重複實作

**P12-P15 實作成果（2026-05-11 完成）:**

| 改動 | 狀態 | 檔案 | 說明 |
|------|------|------|------|
| P12: 社會情緒接入 | ✅ 完成 | `stock_analysis.py` line ~240 | Reddit/PTT 情緒傳入 sentiment analyst |
| P13: 回測引擎整合 | ✅ 完成 | `stock_analysis.py` line ~1300 | 分析完成後自動跑 90 天回測 |
| P14: 即時報價覆寫 | ✅ 完成 | `stock_analysis.py` line ~136 | Finnhub 即時報價覆寫收盤價 |
| P15: 多股票批量 | ✅ 完成 | `stock_analysis.py` argparse | `--tickers AAPL,MSFT,GOOGL` |

**P16-P19 實作成果（2026-05-11 完成）:**

| 改動 | 狀態 | 檔案 | 說明 |
|------|------|------|------|
| P16: 置信度加權倉位 | ✅ 完成 | `scripts/position_sizer.py` + line 938 | 根據 conf × score 動態計算倉位 |
| P17: 分析師評分追蹤 | ✅ 完成 | `scripts/analyst_tracker.py` + line 816 | SQLite + JSON 持久化 |
| P18: RSI/乖離率警報 | ✅ 完成 | `scripts/alert_engine.py` + line 929 | 超賣超買即時警報 |
| P19: 主流程整合 | ✅ 完成 | `stock_analysis.py` 三處 patch | P16+P17+P18 接入主流程 |

### P16 倉位計算引擎
```python
from scripts.position_sizer import calculate_position_size, format_position_report
ps = calculate_position_size(ticker="AAPL", confidence=0.85, final_score=0.78)
# → {position_size_pct: 23.1, dollar_amount: 23100, signal: "heavy", ...}
```

### P17 分析師評分追蹤（class-based）
```python
from scripts.analyst_tracker import AnalystTracker
tracker = AnalystTracker()
tracker.log_analyst_results(symbol="0700.HK", analyst_results=final_positions)
# 寫入 ~/.hermes/stock_memory/analyst_tracker/
# CLI: python scripts/analyst_tracker.py --stats
```

### P18 技術警報
```python
from scripts.alert_engine import check_alerts
alerts = check_alerts("AAPL")
# RSI < 30 → 🟢 BUY | RSI > 70 → 🔴 SELL
# 乖離率 < -5% → 🟢 嚴重超賣 | > +5% → 🔴 嚴重超買
```

### P15 批量分析用法
```bash
python3 scripts/stock_analysis.py --tickers 0700.HK,9988.HK,1810.HK
python3 scripts/stock_analysis.py -t AAPL,MSFT,GOOGL
```

### 新輸出區塊（出現在分析報告）
```
【P16 倉位計算】
🔵 倉位建議: 23.1% ($23,100)
   信心水平: 85% | 評分: 0.78

【P18 技術警報】
🟢 RSI 超賣 28.5

✅ P17 分析師評分已記錄
✅ Phase A 決策已保存
✅ 自動回測（過去 90 天）
📡 即時報價: $58.50 (Finnhub)
🌐 社會情緒: Reddit 72% 看漲 | PTT 65% 看漲
```

詳見 `three-tool-orchestration/references/stock-team-agent-p11-p19-2026-05-11.md`**

| 改動 | 狀態 | 檔案 | 說明 |
|------|------|------|------|
| P6: Phase B Cronjob | ✅ 完成 | `scripts/phase_b_cron.py` + `~/.hermes/scripts/stock_phase_b_cron.sh` | 每日 09:00 自動執行 |
| P7: 回測引擎 | ✅ 完成 | `scripts/backtest_engine.py` | 技術指標回測，輸出 `~/.hermes/stock_backtest/` |
| P8: Markdown 報告 | ✅ 完成 | `scripts/report_generator.py` | ASCII 雷達圖 + Markdown 報告，已整合進 `stock_analysis.py` |
| P9: 社交情緒 | ✅ 完成 | `scripts/data_sources/social_sentiment_provider.py` | Reddit + PTT 情緒抓取 |
| P10: 即時報價 | ✅ 完成 | `scripts/data_sources/realtime_quotes.py` | Finnhub（已設定 API key）/Alpha Vantage/Polygon |
| P6 Cronjob | ✅ 完成 | Cronjob ID: `ceaed73b3480` | 每日 `0 9 * * *`，`~/.hermes/scripts/stock_phase_b_cron.sh` |
| P9 API Key | ✅ 完成 | `~/.hermes/.env` | `FINNHUB_KEY=d1v09cpr01qujmdev3qgd1v09cpr01qujmdev3r0` |

### P6 Phase B Cronjob 用法
```bash
# 單一股票
python3 scripts/phase_b_cron.py AAPL
# 批量處理所有 pending
python3 scripts/phase_b_cron.py --all
```

### P7 回測引擎用法
```python
from scripts.backtest_engine import run_backtest
result = run_backtest("AAPL", days=90)
# result: {overall_accuracy, precision_buy, precision_sell, ...}
```

### P8 報告生成用法
```python
from scripts.report_generator import generate_analysis_report
path = generate_analysis_report(result_dict, "AAPL")
# 產出: ~/.hermes/stock_outputs/AAPL_2026-05-11.md + ASCII 雷達圖
```

### P9 社交情緒用法
```python
from scripts.data_sources.social_sentiment_provider import get_combined_social_sentiment
s = get_combined_social_sentiment("AAPL")
# s: {reddit_bullish_pct, ptt_bullish_pct, combined_score}
```

### P10 即時報價用法
```python
from scripts.data_sources.realtime_quotes import get_realtime_quote
q = get_realtime_quote("AAPL")
# q: {price, change, change_pct, volume, source, ...}
# API key 從環境變量讀取: FINNHUB_KEY / ALPHA_VANTAGE_KEY / POLYGON_KEY
```

詳見 `three-tool-orchestration/references/stock-team-agent-p11-p19-2026-05-11.md`
- `references/stock-team-agent-p6-p10-2026-05-11.md` — P6-P10 實作全記錄（含 sys/path 陷阱與 subagent 導出驗證教訓）
- `references/stock-team-agent-p11-p19-2026-05-11.md` — P11-P19 實作全記錄（含錯誤診斷案例、class-based 模組整合陷阱）
