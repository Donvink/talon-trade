#!/usr/bin/env python3
"""
风控检查脚本（硬编码规则，AI无法绕过）
"""

import argparse
import json
import os
from pathlib import Path
from datetime import datetime, date, timedelta
from core.config import DATA_ROOT, DB_PATH, MAX_ORDER_VALUE, MAX_ORDER_SHARES, DAILY_LOSS_LIMIT, MAX_POSITION_PCT, MAX_OPEN_POSITIONS

# 持久化文件
PNL_FILE = DATA_ROOT / "daily_pnl.json"
POSITIONS_FILE = DATA_ROOT / "positions.json"
ORDER_LOG_FILE = DATA_ROOT / "order_log.json"

def load_json(file, default=None):
    if file.exists():
        with open(file, 'r') as f:
            return json.load(f)
    return default if default is not None else {}

def save_json(file, data):
    file.parent.mkdir(parents=True, exist_ok=True)
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

def check_order(order_dict):
    symbol = order_dict.get('symbol')
    quantity = order_dict.get('quantity')
    side = order_dict.get('side', 'BUY')
    order_type = order_dict.get('order_type', 'MARKET')
    limit_price = order_dict.get('limit_price')

    # 模拟获取当前价格（实际应调用行情）
    current_price = 150.0  # 占位

    # 1. 单笔限额
    order_value = quantity * current_price
    if order_value > MAX_ORDER_VALUE:
        return False, f"Order value ${order_value:.2f} exceeds max ${MAX_ORDER_VALUE}"
    if quantity > MAX_ORDER_SHARES:
        return False, f"Order quantity {quantity} exceeds max {MAX_ORDER_SHARES}"

    # 2. 每日亏损熔断
    pnl_data = load_json(PNL_FILE, {})
    today = str(date.today())
    daily_pnl = pnl_data.get(today, 0)
    if daily_pnl <= -DAILY_LOSS_LIMIT:
        return False, f"Daily loss limit reached: {daily_pnl} <= -{DAILY_LOSS_LIMIT}"

    # 3. 持仓集中度（买入时）
    if side == 'BUY':
        positions = load_json(POSITIONS_FILE, {})
        # 假设账户总值100000（实际应从IBKR获取）
        account_value = 100000
        new_position_value = current_price * quantity
        current_position_value = positions.get(symbol, {}).get('quantity', 0) * current_price
        if (current_position_value + new_position_value) / account_value * 100 > MAX_POSITION_PCT:
            return False, f"Position in {symbol} would exceed {MAX_POSITION_PCT}% of portfolio"

    # 4. 持仓数量限制
    if side == 'BUY':
        positions = load_json(POSITIONS_FILE, {})
        if len(positions) >= MAX_OPEN_POSITIONS and symbol not in positions:
            return False, f"Maximum open positions ({MAX_OPEN_POSITIONS}) reached"

    # 5. 订单频率检查
    order_log = load_json(ORDER_LOG_FILE, [])
    now = datetime.now()
    one_min_ago = now - timedelta(minutes=1)
    one_hour_ago = now - timedelta(hours=1)
    orders_last_min = [o for o in order_log if datetime.fromisoformat(o['time']) > one_min_ago]
    orders_last_hour = [o for o in order_log if datetime.fromisoformat(o['time']) > one_hour_ago]
    if len(orders_last_min) >= 5:
        return False, "Too many orders in last minute"
    if len(orders_last_hour) >= 20:
        return False, "Too many orders in last hour"

    # 记录订单
    order_log.append({'time': now.isoformat(), 'order': order_dict})
    save_json(ORDER_LOG_FILE, order_log)
    return True, "Approved"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--order", help="Order JSON string")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.check:
        if not args.order:
            print(json.dumps({"error": "Missing --order"}))
            sys.exit(1)
        try:
            order = json.loads(args.order)
        except:
            print(json.dumps({"error": "Invalid JSON"}))
            sys.exit(1)
        ok, msg = check_order(order)
        print(json.dumps({"approved": ok, "message": msg}))
    elif args.status:
        pnl_data = load_json(PNL_FILE, {})
        today = str(date.today())
        positions = load_json(POSITIONS_FILE, {})
        status = {
            "daily_pnl": pnl_data.get(today, 0),
            "daily_loss_limit": DAILY_LOSS_LIMIT,
            "positions": positions,
            "max_positions": MAX_OPEN_POSITIONS
        }
        print(json.dumps(status, indent=2))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()