# short_term_screener.py
import json
import sys
from pathlib import Path
from datetime import datetime

# 导入你的现有模块
from data_manager import DataManager
from stock_pool import get_sp500_symbols
from rps_calculator import calc_returns, calc_rps_for_all
from short_term_strategies import momentum_breakout

def main():
    dm = DataManager()
    symbols = get_sp500_symbols()
    results = []

    # 预计算所有股票的RPS（可复用 screener.py 中的逻辑）
    returns_dict = {}
    for sym in symbols:
        df = dm.get_data(sym)
        if len(df) < 250:   # 需要足够数据
            continue
        ret = calc_returns(df)
        returns_dict[sym] = ret

    rps_all = calc_rps_for_all(returns_dict)

    # 为每只股票获取最新数据并应用策略
    for sym in symbols:
        if sym not in rps_all:
            continue
        rps = rps_all[sym]
        df = dm.get_data(sym)
        if len(df) < 21:
            continue
        signal, price, reason = momentum_breakout(
            df,
            rps['20d_rps'], rps['60d_rps'],
            rps['120d_rps'], rps['250d_rps']
        )
        if signal:
            results.append({
                'symbol': sym,
                'price': price,
                'reason': reason,
                'rps': rps,
                'date': df.index[-1].strftime('%Y-%m-%d')
            })

    # 保存结果
    output = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'signals': results
    }
    with open(Path(dm.db_path).parent / "short_term_signals.json", 'w') as f:
        json.dump(output, f, indent=2)

    print(json.dumps(output, indent=2))
    dm.close()

if __name__ == '__main__':
    main()