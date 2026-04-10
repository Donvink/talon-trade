#!/usr/bin/env python3
"""
RPS选股主程序
"""

import json
import sys
from datetime import datetime
from core.config import RPS_THRESHOLD, RPS_PERIODS, CACHE_DIR
from core.data_manager import DataManager
from core.stock_pool import get_sp500_symbols
from core.rps_calculator import calc_returns, calc_rps_for_all
from core.factors import score_stock

def main():
    dm = DataManager()
    symbols = get_sp500_symbols()
    print(f"股票池大小: {len(symbols)}")

    # 计算每只股票的涨幅
    returns_dict = {}
    for sym in symbols:
        df = dm.get_data(sym)
        if len(df) < max(RPS_PERIODS):
            print(f"{sym}: 数据不足，跳过")
            continue
        ret = calc_returns(df)
        returns_dict[sym] = ret
    print(f"有效股票: {len(returns_dict)}")

    # 计算RPS
    rps_all = calc_rps_for_all(returns_dict)

    # 计算综合得分
    candidates = []
    for sym in symbols:
        if sym not in rps_all:
            continue
        rps_scores = rps_all[sym]
        # 要求所有周期RPS均大于阈值
        if all(rps_scores.get(f'{p}d_rps', 0) >= RPS_THRESHOLD for p in RPS_PERIODS):
            df = dm.get_data(sym)
            current_date = df.index[-1].strftime('%Y-%m-%d')
            total_score = score_stock(sym, df, rps_scores, as_of_date=current_date)
            candidates.append({
                'symbol': sym,
                'rps_scores': rps_scores,
                'total_score': total_score
            })

    # 按总分排序
    candidates.sort(key=lambda x: x['total_score'], reverse=True)

    result = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'total_stocks': len(returns_dict),
        'candidates': [c['symbol'] for c in candidates],
        'details': {c['symbol']: c for c in candidates}
    }

    # 保存结果到JSON
    output_path = CACHE_DIR / "rps_candidates.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    dm.close()

if __name__ == '__main__':
    main()