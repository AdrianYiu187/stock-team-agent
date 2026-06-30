"""v5.20 _json_safe(np.bool_) Bug Fix — Permanent Regression Guard.

背景 (2026-06-30 E2E AAPL 揭露):
  - backtest 結果的 buy_correct / sell_correct 等是 numpy.bool_
  - stock_analysis.py 第 1984 行 json.dump(_result, ...) 直接失敗
  - E2E 看到 `⚠️ JSON保存失敗: Object of type bool is not JSON serializable`
  - backtest_engine.py 的 _json_safe 只處理 np.bool_，但 stock_analysis.py
    完全沒有 _json_safe 保護，且 line 2011 重複 import json (冗餘)

修復:
  - stock_analysis.py 內聯 _json_safe()（lazy numpy import）
  - line 1984 + line 2016 兩處 json.dump 套用
  - 移除 line 2011 冗餘 `import json as _json`

本測試守護:
  1. _json_safe 存在且可調用
  2. 處理 numpy.bool_ 不丟例外
  3. 處理 numpy.integer / numpy.floating / numpy.ndarray
  4. 回退路徑（無 numpy）也能 work（純遞迴 dict/list）
  5. stock_analysis.py line 1984 + line 2016 都套用了 _json_safe
"""

import ast
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent
STOCK_ANALYSIS = SCRIPTS_DIR / "stock_analysis.py"


@pytest.fixture
def stock_analysis_source():
    return STOCK_ANALYSIS.read_text(encoding="utf-8")


def test_json_safe_handles_numpy_bool():
    """核心 fix: _json_safe 必須能轉換 np.bool_ (backtest buy_correct 等返回此型別)。"""
    np = pytest.importorskip("numpy")
    try:
        sys.path.insert(0, str(SCRIPTS_DIR))
        # 由於 _json_safe 是 main() 內嵌套函數，這裡用 import 模組 + 取出函數
        # stock_analysis.py 不導出 _json_safe，所以用 AST + exec 模擬 main scope
        import importlib.util

        spec = importlib.util.spec_from_file_location("sa", STOCK_ANALYSIS)
        sa = importlib.util.module_from_spec(spec)
        # 不執行整個 module（會跑 argparse main）
        # 直接用 AST 抽取 _json_safe 函數定義
        source = STOCK_ANALYSIS.read_text(encoding="utf-8")
        tree = ast.parse(source)

        # 找 main() 內的 _json_safe
        json_safe_nodes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_json_safe":
                json_safe_nodes.append(node)

        assert json_safe_nodes, "_json_safe not found in stock_analysis.py"

        # 把第一個 _json_safe 函數 AST 編譯並提取 closure/namespace
        # 最簡單：直接 exec 第一個定義，注入 numpy 命名空間
        func_code = compile(
            ast.Module(body=[json_safe_nodes[0]], type_ignores=[]),
            "<json_safe_extract>",
            "exec",
        )
        namespace = {"np": np}
        exec(func_code, namespace)
        _json_safe = namespace["_json_safe"]

        # 1. np.bool_ 必須轉成 Python bool
        result = _json_safe(np.bool_(True))
        assert result is True or result is False, f"np.bool_ not converted: {type(result)}"

        # 2. 嵌套 dict + np.bool_ 也能處理
        nested = {"a": np.bool_(True), "b": {"c": np.bool_(False)}}
        out = _json_safe(nested)
        json.dumps(out)  # 不應丟例外

    finally:
        sys.path.pop(0) if sys.path and sys.path[0] == str(SCRIPTS_DIR) else None


def test_json_safe_handles_numpy_integer_floating():
    """_json_safe 也應處理 np.int64 / np.float64（pandas 計算結果常見）。"""
    np = pytest.importorskip("numpy")
    source = STOCK_ANALYSIS.read_text(encoding="utf-8")
    tree = ast.parse(source)
    json_safe_node = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_json_safe"),
        None,
    )
    assert json_safe_node
    namespace = {"np": np}
    exec(
        compile(ast.Module(body=[json_safe_node], type_ignores=[]), "<x>", "exec"),
        namespace,
    )
    _json_safe = namespace["_json_safe"]

    assert _json_safe(np.int64(42)) == 42
    assert _json_safe(np.float64(3.14)) == 3.14
    assert _json_safe(np.array([1, 2, 3])) == [1, 2, 3]


def test_json_safe_fallback_without_numpy():
    """沒有 numpy 時 _json_safe 仍能 work（pure dict/list 遞迴）。"""
    # 用 exec 模擬無 numpy 命名空間
    source = STOCK_ANALYSIS.read_text(encoding="utf-8")
    tree = ast.parse(source)
    json_safe_node = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_json_safe"),
        None,
    )
    assert json_safe_node
    # 不注入 np → 觸發 lazy import ImportError → fallback
    namespace = {}
    exec(
        compile(ast.Module(body=[json_safe_node], type_ignores=[]), "<x>", "exec"),
        namespace,
    )
    _json_safe = namespace["_json_safe"]

    out = _json_safe({"a": 1, "b": [2, 3, {"c": 4}]})
    assert json.dumps(out) == '{"a": 1, "b": [2, 3, {"c": 4}]}'


def test_stock_analysis_uses_json_safe_in_dump(stock_analysis_source):
    """stock_analysis.py line 1984 (analysis_result.json) 必須套用 _json_safe。"""
    assert "_json_safe(_result)" in stock_analysis_source, (
        "analysis_result.json dump 仍用裸 json.dump → v5.20 Bug 未修復"
    )


def test_stock_analysis_bt_dump_uses_json_safe(stock_analysis_source):
    """stock_analysis.py line ~2016 (P13 backtest json) 必須套用 _json_safe。"""
    assert "_json_safe(_bt)" in stock_analysis_source, (
        "P13 backtest json dump 仍用裸 json.dump → v5.20 Bug 未修復"
    )


def test_no_redundant_local_json_import(stock_analysis_source):
    """v5.20: 移除 `import json as _json` 冗餘 import（line 2011 原本位置）。"""
    # 允許頂層 `import json` (line 8)，禁止任何 `import json as _json`
    assert "import json as _json" not in stock_analysis_source, (
        "冗餘 `import json as _json` 應移除，直接用頂層 json"
    )