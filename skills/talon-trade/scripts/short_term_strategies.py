# short_term_strategies.py
import pandas as pd
import numpy as np

def momentum_breakout(df, rps_20d, rps_60d, rps_120d, rps_250d):
    """
    动量突破策略信号
    输入：
        df: DataFrame 包含 'close', 'volume'，索引为日期，已按日期排序
        rps_*: 各周期RPS值（浮点数）
    返回：
        (signal, price, reason)
        signal: 1 买入，0 无信号
        price: 建议买入价（收盘价）
        reason: 触发原因
    """
    # 1. RPS条件
    if not (rps_20d >= 90 and rps_60d >= 90 and rps_120d >= 90 and rps_250d >= 90):
        return 0, None, "RPS不达标"
    
    # 2. 需要足够数据
    if len(df) < 21:
        return 0, None, "数据不足"
    
    # 3. 收盘价创20日新高
    recent_high = df['close'].iloc[-21:-1].max()  # 前20个交易日的最高价
    current_close = df['close'].iloc[-1]
    if current_close <= recent_high:
        return 0, None, "未突破前高"
    
    # 4. 成交量大于5日均量
    avg_volume_5 = df['volume'].iloc[-6:-1].mean()  # 前5个交易日平均
    if df['volume'].iloc[-1] <= avg_volume_5:
        return 0, None, "未放量"
    
    return 1, current_close, "动量突破"

# 你可以在此添加其他策略函数