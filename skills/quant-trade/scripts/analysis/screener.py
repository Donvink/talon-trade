#!/usr/bin/env python3
"""
RPS选股主程序
"""

import json
import sys
from datetime import datetime
from typing import List, Dict, Optional, Any
from core.config import RPS_THRESHOLD, RPS_PERIODS, CACHE_DIR, ORDER_BY
from core.data_manager import DataManager
from core.stock_pool import get_sp500_symbols, get_large_cap_pool
from core.rps_calculator import calc_returns, calc_rps_for_all
from core.factors import score_stock
import pandas as pd

def get_candidates_for_date(
    current_date: datetime,
    stock_data: Dict[str, pd.DataFrame],
    symbols: List[str],
    rps_threshold: float,
    rps_periods: List[int],
    max_candidates: Optional[int] = None,
    order_by: str = "total_score"  # 可选: 'turnover', 'turnover_avg', 'total_score'
) -> List[str]:
    """
    返回当日候选股票列表（按指定规则排序）

    参数:
        current_date: 当前日期（datetime 对象）
        stock_data: 预加载的股票日线数据字典 {symbol: DataFrame}
        symbols: 待筛选的股票代码列表
        rps_threshold: RPS 阈值
        rps_periods: RPS 计算周期列表
        max_candidates: 最多返回数量（None 表示全部）
        order_by: 排序依据，支持 'turnover' (前一日成交额), 'turnover_avg' (5日平均成交额), 'total_score' (综合评分)

    返回:
        按规则排序后的候选股票代码列表
    """
    # 1. 计算涨幅
    returns_dict = {}
    for sym in symbols:
        df = stock_data.get(sym)
        if df is None:
            continue
        df_cut = df[df.index <= current_date]
        if len(df_cut) < max(rps_periods):
            continue
        ret = calc_returns(df_cut)
        returns_dict[sym] = ret

    if not returns_dict:
        return []

    # 2. 计算 RPS
    rps_all = calc_rps_for_all(returns_dict)

    # 3. 筛选 RPS 达标股票，并计算成交额等指标
    candidates_info = []
    for sym in symbols:
        if sym not in rps_all:
            continue
        rps_scores = rps_all[sym]
        if not all(rps_scores.get(f'{p}d_rps', 0) >= rps_threshold for p in rps_periods):
            continue

        df = stock_data.get(sym)
        if df is None:
            continue
        df_cut = df[df.index <= current_date]
        if len(df_cut) < RPS_PERIODS[0]:
            continue

        # 计算成交额
        latest_turnover = df_cut['volume'].iloc[-1] * df_cut['close'].iloc[-1]
        avg_5d_turnover = (df_cut['volume'] * df_cut['close']).rolling(5).mean().iloc[-1]

        # 可选计算综合评分（如果需要）
        total_score = None
        if order_by == 'total_score':
            current_date_str = current_date.strftime('%Y-%m-%d')
            total_score = score_stock(sym, df_cut, rps_scores, as_of_date=current_date_str)

        candidates_info.append({
            'symbol': sym,
            'turnover': latest_turnover,
            'turnover_avg': avg_5d_turnover,
            'total_score': total_score,
            'rps_scores': rps_scores
        })

    # 4. 排序
    if order_by == 'turnover':
        candidates_info.sort(key=lambda x: x['turnover'], reverse=True)
    elif order_by == 'turnover_avg':
        candidates_info.sort(key=lambda x: x['turnover_avg'], reverse=True)
    elif order_by == 'total_score':
        candidates_info.sort(key=lambda x: x['total_score'] if x['total_score'] is not None else 0, reverse=True)
    else:
        raise ValueError(f"Unsupported order_by: {order_by}")

    # 5. 返回代码列表
    result = [item['symbol'] for item in candidates_info]
    if max_candidates is not None:
        result = result[:max_candidates]
    return result


def main():
    """独立运行入口，生成候选股票 JSON 文件"""
    dm = DataManager()
    symbols = get_large_cap_pool()  # 可根据需要切换为 get_sp500_symbols()
    print(f"股票池大小: {len(symbols)}")

    # 预加载所有股票数据
    stock_data = {}
    for sym in symbols:
        df = dm.get_data(sym)
        if len(df) >= max(RPS_PERIODS):
            stock_data[sym] = df

    # 调用核心函数获取候选（按5日平均成交额排序）
    current_date = datetime.now()
    candidates = get_candidates_for_date(
        current_date=current_date,
        stock_data=stock_data,
        symbols=symbols,
        rps_threshold=RPS_THRESHOLD,
        rps_periods=RPS_PERIODS,
        order_by=ORDER_BY
    )

    # 为了保持输出 JSON 中包含详细信息，重新生成 details
    details = {}
    for sym in candidates:
        # 从 stock_data 中提取详细信息
        df = stock_data[sym]
        df_cut = df[df.index <= current_date]
        # 计算RPS（为了输出）
        returns_dict = {}
        for s in symbols:
            d = stock_data.get(s)
            if d is None: continue
            d_cut = d[d.index <= current_date]
            if len(d_cut) < max(RPS_PERIODS): continue
            ret = calc_returns(d_cut)
            returns_dict[s] = ret
        rps_all = calc_rps_for_all(returns_dict) if returns_dict else {}
        rps_scores = rps_all.get(sym, {})
        latest_turnover = df_cut['volume'].iloc[-1] * df_cut['close'].iloc[-1]
        avg_5d_turnover = (df_cut['volume'] * df_cut['close']).rolling(5).mean().iloc[-1]
        total_score = score_stock(sym, df_cut, rps_scores, as_of_date=current_date.strftime('%Y-%m-%d'))
        details[sym] = {
            'rps_scores': rps_scores,
            'total_score': total_score,
            'turnover': latest_turnover,
            'turnover_avg': avg_5d_turnover
        }

    result = {
        'date': current_date.strftime('%Y-%m-%d'),
        'total_stocks': len(stock_data),
        'candidates': candidates,
        'details': details
    }

    output_path = CACHE_DIR / "rps_candidates.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    dm.close()


if __name__ == '__main__':
    main()