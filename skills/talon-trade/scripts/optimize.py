#!/usr/bin/env python3
"""
参数调优脚本（并行版）：搜索最佳退出和选股参数组合
用法: python optimize.py
"""

import sys
import itertools
import pandas as pd
import numpy as np
from pathlib import Path
from joblib import Parallel, delayed

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from backtest import backtest
from stock_pool import get_sp500_symbols
from config import DATA_ROOT

STOCK_POOL = get_sp500_symbols()[:30]

def objective(params):
    """目标函数：运行回测并返回总收益率"""
    # 可根据需要调整股票池规模
    #stock_pool = get_sp500_symbols()[:30]   # 先取前30只快速搜索，得到最优后再改全量验证
    start_date = "2024-01-01"
    end_date = "2026-03-30"
    initial_capital = 100000

    trades, final_value = backtest(
        stock_pool=STOCK_POOL,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        rps_threshold=params['rps_threshold'],
        rps_periods=params['rps_periods'],
        max_buy=params['max_buy'],
        stop_loss_pct=params['stop_loss_pct'],
        take_profit_pct=params['take_profit_pct'],
        trailing_stop_pct=params['trailing_stop_pct'],
        max_hold_days=params['max_hold_days'],
        min_hold_days=params['min_hold_days'],
        use_macd_sell=params['use_macd_sell'],
        commission=0.001
    )
    total_return = (final_value - initial_capital) / initial_capital * 100
    return total_return

def run_single(params):
    """单个参数组合的包装，捕获异常"""
    try:
        ret = objective(params)
        return {**params, 'total_return': ret}
    except Exception as e:
        print(f"Error for {params}: {e}")
        return {**params, 'total_return': -np.inf}

def main():
    # 参数网格（风险参数 + 选股参数）
    param_grid = {
        # 风控参数
        'stop_loss_pct': [-6, -8, -10],
        'take_profit_pct': [20, 25, 30],
        'trailing_stop_pct': [8, 10, 12],
        'max_hold_days': [15, 20, 25],
        'min_hold_days': [2, 3, 5],
        'use_macd_sell': [False],  # 根据前期结果保持关闭
        
        # 选股参数
        'rps_threshold': [80, 85, 90],
        'rps_periods': [
            [20, 60, 120],
            [20, 60, 120, 250]
        ],
        'max_buy': [3, 5]           # 每次买入最多几只股票
    }

    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combinations = list(itertools.product(*values))
    print(f"总参数组合数: {len(combinations)}")

    # 并行执行（使用所有CPU核心，verbose=10显示进度）
    results = Parallel(n_jobs=-1, verbose=10)(
        delayed(run_single)(dict(zip(keys, combo))) for combo in combinations
    )

    # 转换为DataFrame并排序
    df_results = pd.DataFrame(results)
    df_results.sort_values('total_return', ascending=False, inplace=True)
    
    # 显示前10组最佳参数
    print("\n=== Best Parameters ===")
    print(df_results.head(10))
    
    # 保存全部结果
    output_path = DATA_ROOT / "optimization_results.csv"
    df_results.to_csv(output_path, index=False)
    print(f"\nResults saved to {output_path}")

if __name__ == "__main__":
    main()