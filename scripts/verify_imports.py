#!/usr/bin/env python3
"""验证所有模块导入"""

import sys
from pathlib import Path

# 添加 scripts 目录到路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

modules_to_test = [
    ("core.config", "DATA_ROOT"),
    ("core.data_manager", "DataManager"),
    ("core.stock_pool", "get_sp500_symbols"),
    ("core.rps_calculator", "calc_returns"),
    ("core.factors", "score_stock"),
    ("trading.ibkr_client", "execute_order"),
    ("trading.risk_checker", "main"),
    ("trading.stop_loss_monitor", "monitor_and_execute"),
    ("analysis.screener", "main"),
    ("analysis.backtest", "backtest"),
    ("analysis.generate_report", "main"),
    ("analysis.optimize", "main"),
    ("utils.update_fundamentals", "main"),
    ("utils.update_fundamentals_history", "main"),
]

print("=" * 50)
print("验证模块导入")
print("=" * 50)

for module_name, attr_name in modules_to_test:
    try:
        module = __import__(module_name, fromlist=[attr_name])
        if hasattr(module, attr_name):
            print(f"✅ {module_name}.{attr_name}")
        else:
            print(f"⚠️ {module_name} 缺少 {attr_name}")
    except Exception as e:
        print(f"❌ {module_name}: {e}")

print("=" * 50)
print("验证完成")