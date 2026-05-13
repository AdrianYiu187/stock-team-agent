# Stock Team Agent 全面系統審計 — 2026-05-11

## 審計結果摘要

| 項目 | 結果 |
|------|------|
| 檔案數量 | 69 個 .py 檔 |
| 語法檢查 | ✅ 69/69 PASS |
| 安全掃描 | ✅ 全部通過 |
| Import 鏈 | ✅ 11/11 核心模組 PASS |
| 共識引擎 | ✅ 7位分析師完整配置 |

## 已修復的 5 項問題

### Fix 1: checkpoint.py — 2處 bare except
```python
# Before
except:
    pass

# After
except Exception:
    pass
```
位置: l.73, l.181

### Fix 2: stock_analysis.py — import 觸發執行
```python
# 添加 if __name__ == "__main__": guard
# datetime import 從 l.82 移至頂部（l.6）
# 移除重複 import os（l.5 保留，l.30 刪除）
```

### Fix 3: consensus_engine.py — 缺少 macro/news 分析師
```python
# Before: analyst_weights 只有 5 位
self.analyst_weights = {
    "market": {...},
    "technical": {...},
    "fundamental": {...},
    "risk": {...},
    "sentiment": {...},
}

# After: 7位完整配置
self.analyst_weights = {
    "market": {"full": 1.0, "technical": 1.2, "fundamental": 0.5, "risk": 0.8, "sentiment": 0.8, "macro": 0.7, "news": 0.5},
    "technical": {"full": 1.0, "technical": 1.5, "fundamental": 0.5, "risk": 0.6, "sentiment": 0.4, "macro": 0.5, "news": 0.3},
    "fundamental": {"full": 1.0, "technical": 0.5, "fundamental": 1.5, "risk": 1.0, "sentiment": 0.5, "macro": 0.6, "news": 0.4},
    "risk": {"full": 1.2, "technical": 0.8, "fundamental": 1.0, "risk": 1.5, "sentiment": 0.6, "macro": 0.8, "news": 0.5},
    "sentiment": {"full": 0.8, "technical": 0.4, "fundamental": 0.5, "risk": 0.5, "sentiment": 1.5, "macro": 0.5, "news": 0.7},
    "macro": {"full": 0.8, "technical": 0.5, "fundamental": 0.6, "risk": 0.8, "sentiment": 0.5, "macro": 1.2, "news": 0.6},
    "news": {"full": 0.7, "technical": 0.3, "fundamental": 0.4, "risk": 0.5, "sentiment": 0.7, "macro": 0.6, "news": 1.2},
}
```

### Fix 4: consensus_engine.py — min_analysts 門檻過低
```python
# Before
self.min_analysts = 2  # 最少需要2位分析師

# After
self.min_analysts = 4  # 最少需要4位分析師（7位中至少過半）
```

### Fix 5: backtest_engine.py — MACD dir() 邏輯錯誤
```python
# Before (BUG: Python dir() 在函數返回時總是包含所有局部變量，導致條件恆真)
return macd_line, signal_full if 'signal_full' in dir() else np.full_like(macd_line, np.nan), macd_hist

# After (正確: signal_full 必然存在)
return macd_line, signal_full, macd_hist
```

## 審計方法論

### Phase 1: 結構掃描
```bash
find scripts -name "*.py" -not -path "*/__pycache__/*" | sort | wc -l
```

### Phase 2: 安全掃描
```python
# bare except 掃描
import glob, re
pattern = re.compile(r'except:\s*\n')
for f in glob.glob('**/*.py', recursive=True):
    if '__pycache__' in f: continue
    with open(f) as fp:
        content = fp.read()
        for m in re.finditer(r'except:\s*\n', content):
            line_no = content[:m.start()].count('\n') + 1
            print(f'{f}:{line_no}')
```

### Phase 3: 語法全面檢查
```python
import py_compile, glob
bad = []
for f in sorted(glob.glob('scripts/**/*.py', recursive=True)):
    if '__pycache__' in f: continue
    try:
        py_compile.compile(f, doraise=True)
    except Exception as e:
        bad.append(f'{f}: {str(e)[:60]}')
```

### Phase 4: Import 鏈驗證
```python
import sys; sys.path.insert(0, 'scripts')
from train.consensus_engine import ConsensusEngine
e = ConsensusEngine()
assert len(e.analyst_weights) == 7, f'Expected 7, got {len(e.analyst_weights)}'
```

### Phase 5: 計算邏輯驗證
```python
import numpy as np
from backtest_engine import calculate_macd
prices = np.array([...])
macd_line, signal_line, hist = calculate_macd(prices)
assert not np.all(np.isnan(signal_line)), "Signal line all NaN"
```

## 未修改的項目（無風險）

| 項目 | 說明 | 風險 |
|------|------|------|
| `train/consensus_engine.py` 缺少 Pydantic validation | `integrate()` 無驗證 | 低（现有 `get()` fallback） |
| `辯論/__init__.py` 是 backward compat shim | 僅2行轉發到 `train/llm_debate_engine.py` | 無 |

## Git Staged 狀態

```
scripts/backtest_engine.py        | 2 +-
scripts/checkpoint.py             | 4 +-
scripts/stock_analysis.py         | 2112 +++++++++++++++++++--
scripts/train/consensus_engine.py | 14 +-
4 files changed, 1068 insertions(+), 1064 deletions(-)
```

## 共識引擎驗證代碼

```python
import sys; sys.path.insert(0, 'scripts')
from train.consensus_engine import ConsensusEngine

e = ConsensusEngine()
print(f'分析師數: {len(e.analyst_weights)} (應為7)')
print(f'min_analysts: {e.min_analysts} (應為4)')
print(f'macro weight: {e.analyst_weights["macro"]["full"]}')
print(f'news weight: {e.analyst_weights["news"]["full"]}')
print(f'dimensions: {e.dimensions}')
print(f'consensus_threshold: {e.consensus_threshold}')
```
