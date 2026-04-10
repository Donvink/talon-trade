#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
SKILL_SCRIPTS = PROJECT_ROOT / "skills" / "quant-trade" / "scripts"

def run_cmd(cmd, description):
    print(f"\n=== {description} ===")
    result = subprocess.run(cmd, shell=True, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"❌ {description} 失败")
        sys.exit(1)
    else:
        print(f"✅ {description} 成功")

if __name__ == "__main__":
    # 1. 下载少量数据
    run_cmd('python -c "import sys; sys.path.insert(0, str(SKILL_SCRIPTS)); from data_manager import DataManager; from stock_pool import get_sp500_symbols; dm = DataManager(); dm.download_full_history(get_sp500_symbols()[:5], years_back=1); dm.close()"', "数据下载")
    # 2. 选股
    run_cmd(f'python {SKILL_SCRIPTS}/screener.py', "RPS选股")
    # 3. 回测
    run_cmd(f'python {SKILL_SCRIPTS}/backtest.py', "回测")
    # 4. 模拟交易
    run_cmd(f'python {SKILL_SCRIPTS}/ibkr_client.py --dry-run --order --symbol AAPL --side BUY --quantity 10', "模拟交易")
    # 5. 风控检查
    run_cmd(f'python {SKILL_SCRIPTS}/risk_checker.py --status', "风控状态")
    print("\n🎉 所有测试完成！")