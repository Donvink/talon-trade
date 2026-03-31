#!/usr/bin/env python3
"""
RPS（相对强度）指标计算
"""

import numpy as np
from config import RPS_PERIODS

def calc_returns(df):
    """
    计算指定周期的涨跌幅
    df: DataFrame with 'close' column, index is date
    返回字典：{'ret_20d': value, 'ret_60d': ...}
    """
    ret = {}
    close = df['adj_close']
    for period in RPS_PERIODS:
        if len(df) >= period:
            ret[f'ret_{period}d'] = (close.iloc[-1] - close.iloc[-period]) / close.iloc[-period] * 100
        else:
            ret[f'ret_{period}d'] = np.nan
    return ret

def calc_rps_for_all(returns_dict):
    """
    输入：{symbol: {ret_20d: ..., ret_60d: ...}}
    输出：{symbol: {'20d_rps': value, '60d_rps': value, ...}}
    """
    rps_all = {}
    for period in RPS_PERIODS:
        key = f'ret_{period}d'
        # 收集所有股票该周期的涨幅（排除NaN）
        values = [r[key] for r in returns_dict.values() if not np.isnan(r[key])]
        if not values:
            continue
        sorted_vals = sorted(values)
        for sym, ret in returns_dict.items():
            if np.isnan(ret[key]):
                rps_all.setdefault(sym, {})[f'{period}d_rps'] = 0
            else:
                rank = sum(1 for v in sorted_vals if v < ret[key]) + 1
                percentile = rank / len(sorted_vals) * 100
                rps_all.setdefault(sym, {})[f'{period}d_rps'] = round(percentile, 2)
    return rps_all