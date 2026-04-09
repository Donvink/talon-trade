#!/usr/bin/env python3
"""
止损止盈监控：使用本地数据库价格
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from trading.ibkr_client import connect_ib, place_order
from core.config import STOP_LOSS_PCT, TAKE_PROFIT_PCT
from core.data_manager import DataManager


def get_latest_close(symbol):
    """从本地数据库获取最新收盘价"""
    dm = DataManager()
    df = dm.get_data(symbol)
    dm.close()
    if df.empty:
        return None
    return df['adj_close'].iloc[-1]


def monitor_and_execute():
    """监控持仓并执行止损止盈（使用本地收盘价）"""
    ib = None
    try:
        ib = connect_ib()
        
        # 从 IBKR 获取实时持仓
        positions = ib.positions()
        
        if not positions:
            print("当前无持仓")
            return
        
        print(f"检查 {len(positions)} 个持仓...")
        
        for pos in positions:
            symbol = pos.contract.symbol
            quantity = pos.position
            avg_cost = pos.avgCost
            
            if quantity == 0:
                continue
            
            # 使用本地数据库的最新收盘价
            current_price = get_latest_close(symbol)
            if current_price is None:
                print(f"无法获取 {symbol} 历史价格，跳过")
                continue
            
            # 计算盈亏百分比
            if avg_cost > 0:
                pnl_pct = (current_price - avg_cost) / avg_cost * 100
            else:
                continue
            
            print(f"{symbol}: 成本=${avg_cost:.2f}, 最新收盘价=${current_price:.2f}, 盈亏={pnl_pct:.2f}%")
            
            # 检查止损
            if pnl_pct <= STOP_LOSS_PCT:
                print(f"⚠️ 触发止损: {symbol} 亏损 {pnl_pct:.2f}%")
                result = place_order(ib, symbol, "SELL", abs(quantity), "MARKET")
                print(f"止损单已提交: {result}")
            
            # 检查止盈
            elif pnl_pct >= TAKE_PROFIT_PCT:
                print(f"✅ 触发止盈: {symbol} 盈利 {pnl_pct:.2f}%")
                result = place_order(ib, symbol, "SELL", abs(quantity), "MARKET")
                print(f"止盈单已提交: {result}")
        
        print("监控检查完成")
        
    except Exception as e:
        print(f"监控执行失败: {e}")
    finally:
        if ib:
            ib.disconnect()


if __name__ == "__main__":
    monitor_and_execute()