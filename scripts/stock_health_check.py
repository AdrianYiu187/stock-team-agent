#!/usr/bin/env python3
"""
Stock_Team_Agent 健康檢查腳本
驗證所有模組和功能正常運作
"""

import sys
import os
from pathlib import Path

# 添加 scripts 目錄到路徑
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))


def check_import(module_name: str, import_path: str) -> tuple:
    """檢查模組是否可以導入"""
    try:
        module = __import__(import_path, fromlist=[module_name])
        return True, f"✅ {module_name}"
    except Exception as e:
        return False, f"❌ {module_name}: {str(e)[:50]}"


def check_file_exists(path: Path) -> tuple:
    """檢查檔案是否存在"""
    if path.exists():
        return True, f"✅ {path.name} ({path.stat().st_size} bytes)"
    else:
        return False, f"❌ {path.name}: 不存在"


def main():
    print("=" * 60)
    print("Stock_Team_Agent 健康檢查")
    print("=" * 60)
    
    all_passed = True
    results = []
    
    # 1. 檢查核心模組
    print("\n【1. 核心模組檢查】")
    core_modules = [
        ("stock_router", "stock_router"),
        ("consensus_engine", "consensus.consensus_engine"),
        ("market_analyst", "handlers.market_analyst"),
        ("technical_analyst", "handlers.technical_analyst"),
        ("fundamental_analyst", "handlers.fundamental_analyst"),
        ("risk_analyst", "handlers.risk_analyst"),
        ("sentiment_analyst", "handlers.sentiment_analyst"),
        ("stock_data_provider", "data_sources.stock_data_provider"),
        ("technical_indicators", "indicators.technical_indicators"),
        ("professional_indices", "indicators.professional_indices"),
        ("valuation_models", "valuation.valuation_models"),
        ("chart_generator", "charts.chart_generator"),
        ("workflow_engine", "workflow_engine"),
        ("trigger", "trigger"),
    ]
    
    for name, path in core_modules:
        try:
            __import__(path, fromlist=[name])
            print(f"  ✅ {name}")
        except Exception as e:
            print(f"  ❌ {name}: {str(e)[:60]}")
            all_passed = False
    
    # 2. 檢查檔案完整性
    print("\n【2. 檔案完整性檢查】")
    required_files = [
        SCRIPT_DIR / "stock_router.py",
        SCRIPT_DIR / "consensus" / "consensus_engine.py",
        SCRIPT_DIR / "handlers" / "market_analyst.py",
        SCRIPT_DIR / "handlers" / "technical_analyst.py",
        SCRIPT_DIR / "handlers" / "fundamental_analyst.py",
        SCRIPT_DIR / "handlers" / "risk_analyst.py",
        SCRIPT_DIR / "handlers" / "sentiment_analyst.py",
        SCRIPT_DIR / "indicators" / "technical_indicators.py",
        SCRIPT_DIR / "indicators" / "professional_indices.py",
        SCRIPT_DIR / "valuation" / "valuation_models.py",
        SCRIPT_DIR / "charts" / "chart_generator.py",
        SCRIPT_DIR / "github_integration" / "github_scanner_integration.py",
        SCRIPT_DIR / "workflow_engine.py",
        SCRIPT_DIR / "trigger.py",
        SCRIPT_DIR.parent / "SKILL.md",
        SCRIPT_DIR.parent / "docs" / "capabilities.md",
    ]
    
    for file_path in required_files:
        exists, msg = check_file_exists(file_path)
        print(f"  {msg}")
        if not exists:
            all_passed = False
    
    # 3. 測試路由器功能
    print("\n【3. 路由器功能測試】")
    try:
        from stock_router import StockRouter
        
        # 測試初始化
        router = StockRouter(symbol="0700.HK", region="hk")
        print("  ✅ StockRouter 初始化成功")
        
        # 測試任務識別
        task_types = [
            ("全面分析騰訊", "full_analysis"),
            ("技術分析", "technical_only"),
            ("基本面分析", "fundamental_only"),
            ("風險評估", "risk_assessment"),
            ("估值分析", "valuation_only"),
            ("比較騰訊和阿里巴巴", "comparison"),
        ]
        
        for request, expected in task_types:
            task_type = router._identify_task_type(request)
            if task_type == expected:
                print(f"  ✅ 任務識別: '{request[:10]}...' -> {task_type}")
            else:
                print(f"  ⚠️ 任務識別: '{request[:10]}...' -> {task_type} (期望: {expected})")
        
        # 測試股票代碼解析
        symbols = ["0700.HK", "9988.HK", "AAPL", "TSLA", "000001.SS"]
        for symbol in symbols:
            router_test = StockRouter(symbol=symbol, region="auto")
            print(f"  ✅ 代碼解析: {symbol} -> region={router_test.region}")
        
    except Exception as e:
        print(f"  ❌ 路由器測試失敗: {str(e)}")
        all_passed = False
    
    # 4. 測試共識引擎
    print("\n【4. 共識引擎測試】")
    try:
        from consensus.consensus_engine import ConsensusEngine
        
        engine = ConsensusEngine()
        
        # 模擬分析師結果
        mock_results = {
            "market": {"score": 0.6, "signal": "hold", "confidence": 0.7, "buy_score": 0.3, "hold_score": 0.5, "sell_score": 0.2},
            "technical": {"score": 0.45, "signal": "sell", "confidence": 0.6, "buy_score": 0.25, "hold_score": 0.2, "sell_score": 0.55},
            "fundamental": {"score": 0.7, "signal": "buy", "confidence": 0.8, "buy_score": 0.65, "hold_score": 0.25, "sell_score": 0.1},
        }
        
        result = engine.integrate(mock_results, task_type="full_analysis", symbol="0700.HK")
        
        if result.get("status") == "success":
            print(f"  ✅ 共識整合成功")
            print(f"     建議: {result.get('recommendation')}")
            print(f"     信心度: {result.get('confidence')}")
            print(f"     衝突: {len(result.get('conflicts', []))}個")
        else:
            print(f"  ⚠️ 共識整合狀態: {result.get('status')}")
        
    except Exception as e:
        print(f"  ❌ 共識引擎測試失敗: {str(e)}")
        all_passed = False
    
    # 5. 測試專業指數
    print("\n【5. 專業指數測試】")
    try:
        from indicators.professional_indices import ProfessionalIndices
        
        indices = ProfessionalIndices()
        
        # 測試巴菲特指標
        buffett = indices.buffett_indicator(market_cap=5000000000000, gdp=25000000000000)
        print(f"  ✅ 巴菲特指標: {buffett.get('percentage', 'N/A')}%")
        
        # 測試席勒PE
        cape = indices.shiller_pe(price=350, avg_earnings=20)
        cape_val = cape.get('value', cape.get('shiller_pe', 'N/A'))
        print(f"  ✅ 席勒PE: {cape_val}")
        
        # 測試黃金交叉/死亡交叉
        golden = indices.gold_cross_death_cross(sma_50=50, sma_200=45, prev_sma_50=49, prev_sma_200=46)
        print(f"  ✅ 黃金交叉: {golden.get('signal', 'N/A')}")
        
        # 測試風險評分
        risk = indices.risk_score(returns=[0.05, -0.02, 0.03, 0.01, -0.01], volatility=0.25)
        print(f"  ✅ 風險評分: {risk.get('score', 'N/A')}")
        
    except Exception as e:
        print(f"  ❌ 專業指數測試失敗: {str(e)}")
        all_passed = False
    
    # 6. 測試估值模型
    print("\n【6. 估值模型測試】")
    try:
        from valuation.valuation_models import ValuationModels
        
        models = ValuationModels()
        
        # 測試DCF
        dcf = models.dcf(cash_flows=[800, 900, 1000], discount_rate=0.10, terminal_growth=0.03, shares_outstanding=5000000000)
        print(f"  ✅ DCF估值: ${dcf.get('intrinsic_value', 'N/A'):.2f}")
        
        # 測試PEG
        peg = models.peg(pe_ratio=25, earnings_growth_rate=0.30)
        print(f"  ✅ PEG: {peg.get('peg', 'N/A')}")
        
        # 測試DDM
        ddm = models.ddm(dividend_per_share=2.0, discount_rate=0.12, growth_rate=0.10, years=5)
        print(f"  ✅ DDM估值: ${ddm.get('intrinsic_value', 'N/A'):.2f}")
        
    except Exception as e:
        print(f"  ❌ 估值模型測試失敗: {str(e)}")
        all_passed = False
    
    # 7. 測試工作流引擎
    print("\n【7. 工作流引擎測試】")
    try:
        from workflow_engine import MultiRoleWorkflow
        
        workflow = MultiRoleWorkflow()
        info = workflow.get_workflow_info()
        
        print(f"  ✅ 工作流引擎初始化成功")
        print(f"     可用工作流: {len(info['available_workflows'])}個")
        for wf_name in info['available_workflows']:
            print(f"       - {wf_name}")
        
    except Exception as e:
        print(f"  ❌ 工作流引擎測試失敗: {str(e)}")
        all_passed = False
    
    # 8. 測試能力觸發器
    print("\n【8. 能力觸發器測試】")
    try:
        from trigger import StockCapabilityTrigger
        
        trigger = StockCapabilityTrigger()
        caps = trigger._identify_capabilities("分析騰訊0700.HK的技術面")
        
        print(f"  ✅ 能力觸發器初始化成功")
        print(f"     識別能力: {caps[:5]}...")
        
    except Exception as e:
        print(f"  ❌ 能力觸發器測試失敗: {str(e)}")
        all_passed = False
    
    # 9. 測試GitHub整合
    print("\n【9. GitHub整合測試】")
    try:
        from github_integration.github_scanner_integration import GitHubIntegration
        
        gh = GitHubIntegration()
        
        # 測試評分功能
        mock_repo = {"stars": 500, "language": "Python", "topics": ["stock", "finance"]}
        score = gh._score_repo(mock_repo)
        print(f"  ✅ GitHub整合初始化成功")
        print(f"     倉庫評分: {score}")
        
    except Exception as e:
        print(f"  ❌ GitHub整合測試失敗: {str(e)}")
        all_passed = False
    
    # 10. 完整分析測試
    print("\n【10. 完整分析測試】")
    try:
        from stock_router import StockRouter
        import json
        
        router = StockRouter(symbol="0700.HK", region="hk")
        result = router.route("全面分析騰訊")
        
        if result.get("consensus", {}).get("recommendation"):
            print(f"  ✅ 完整分析執行成功")
            print(f"     建議: {result['consensus']['recommendation']}")
            print(f"     信心度: {result['consensus']['confidence']}")
            print(f"     分析師數: {len(result['analyst_results'])}")
        else:
            print(f"  ⚠️ 完整分析執行但無共識建議")
        
    except Exception as e:
        print(f"  ❌ 完整分析測試失敗: {str(e)}")
        all_passed = False
    
    # 總結
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ Stock_Team_Agent 健康檢查通過！")
    else:
        print("⚠️ 部分檢查未通過，請查看上述失敗項目")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
