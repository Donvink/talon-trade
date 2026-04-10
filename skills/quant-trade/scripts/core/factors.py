#!/usr/bin/env python3
"""
多因子评分：结合成交量、基本面等
"""

from datetime import datetime

import datetime

import yfinance as yf
import numpy as np
from core.config import RPS_THRESHOLD
from core.data_manager import DataManager

def calc_volume_factor(df):
    """成交量因子：当前成交量/20日均量"""
    vol = df['volume']
    avg_vol = vol.rolling(20).mean()
    if not avg_vol.isna().iloc[-1]:
        ratio = vol.iloc[-1] / avg_vol.iloc[-1]
        # 归一化到0-100，>2倍给100分
        return min(ratio, 2) / 2 * 100
    return 50

def fetch_fundamentals_at_date(symbol, date_str):
    """从数据库获取指定日期前的最新基本面数据"""
    dm = DataManager()
    fund = dm.get_fundamentals_at_date(symbol, date_str)
    dm.close()
    if fund:
        return fund['pe'], fund['roe']
    return None, None

def score_stock(symbol, df, rps_scores, as_of_date, use_fundamentals=False):
    """
    综合评分（使用历史基本面数据）
    as_of_date: 当前交易日（字符串 YYYY-MM-DD），用于匹配基本面快照
    """
    rps_avg = np.mean(list(rps_scores.values()))
    vol_score = calc_volume_factor(df)

    if use_fundamentals:
        pe, roe = fetch_fundamentals_at_date(symbol, as_of_date)
        if pe is None or pe <= 0:
            pe_score = 50
        else:
            pe_score = max(0, min(100, (30 - pe) / 20 * 100))
        if roe is None:
            roe_score = 50
        else:
            roe_score = min(100, roe / 15 * 100)
        fundamental_score = (pe_score + roe_score) / 2
    else:
        fundamental_score = 50

    total = rps_avg * 0.5 + vol_score * 0.2 + fundamental_score * 0.3
    return total
