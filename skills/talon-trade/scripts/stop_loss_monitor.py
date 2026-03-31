#!/usr/bin/env python3
"""
止损止盈监控：定期检查持仓价格，触发平仓
"""

import json
import os
from pathlib import Path
from config import DATA_ROOT, STOP_LOSS_PCT, TAKE_PROFIT_PCT
from ibkr_client import connect_ib, place_order

POSITIONS_FILE = DATA_ROOT / "positions.json"

def monitor_and_execute():
    if not POSITIONS_FILE.exists():
        return
    with open(POSITIONS_FILE, 'r') as f:
        positions = json.load(f)

    # 连接IBKR
    ib = connect_ib()
    for sym, pos in positions.items():
        # 获取当前价格（简化：从IBKR获取）
        # 这里需要实现获取实时价格的逻辑，此处占位
        current_price = 150.0
        entry_price = pos.get('entry_price', 0)
        if entry_price == 0:
            continue
        pnl_pct = (current_price - entry_price) / entry_price * 100
        if pnl_pct <= STOP_LOSS_PCT:
            print(f"Stop loss triggered for {sym}")
            place_order(ib, sym, "SELL", pos['quantity'], "MARKET")
            del positions[sym]
        elif pnl_pct >= TAKE_PROFIT_PCT:
            print(f"Take profit triggered for {sym}")
            place_order(ib, sym, "SELL", pos['quantity'], "MARKET")
            del positions[sym]

    # 保存更新后的持仓
    with open(POSITIONS_FILE, 'w') as f:
        json.dump(positions, f)
    ib.disconnect()

if __name__ == "__main__":
    monitor_and_execute()