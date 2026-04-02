#!/usr/bin/env python3
"""
Interactive Brokers 交易客户端
支持模拟盘和实盘，支持 dry-run 模式和小数股
用法:
  python ibkr_client.py --connect [--host 127.0.0.1 --port 7497 --client-id 1]
  python ibkr_client.py --order --symbol AAPL --side BUY --quantity 10 --type MARKET [--dry-run]
  python ibkr_client.py --positions
  python ibkr_client.py --account
  python ibkr_client.py --dry-run --order --symbol AAPL --side BUY --quantity 0.5 --type MARKET
"""

import argparse
import json
import sys
from pathlib import Path

# 添加当前目录到路径以便导入 config
sys.path.insert(0, str(Path(__file__).parent))

from ib_insync import IB, Stock, MarketOrder, LimitOrder, StopOrder
from config import IBKR_HOST, IBKR_PORT, IBKR_CLIENT_ID, IBKR_TIMEOUT

# 全局连接
_ib = None


def connect_ib(host=None, port=None, client_id=None, timeout=None):
    """连接到 IB TWS/Gateway"""
    host = host or IBKR_HOST
    port = port or IBKR_PORT
    client_id = client_id or IBKR_CLIENT_ID
    timeout = timeout or IBKR_TIMEOUT

    ib = IB()
    try:
        print(f"正在连接 {host}:{port} clientId={client_id}...")
        ib.connect(host, port, clientId=client_id, timeout=timeout)
        print(f"✅ 连接成功")
        return ib
    except Exception as e:
        print(json.dumps({"error": f"Failed to connect: {str(e)}"}))
        sys.exit(1)


def get_ib():
    """获取或创建全局 IB 连接"""
    global _ib
    if _ib is None or not _ib.isConnected():
        _ib = connect_ib()
    return _ib


def disconnect_ib():
    """断开连接"""
    global _ib
    if _ib is not None:
        _ib.disconnect()
        _ib = None


def get_account_cash(ib):
    """获取账户可用现金"""
    try:
        account_values = ib.accountValues()
        for value in account_values:
            if value.tag == 'TotalCashBalance':
                return float(value.value)
        return None
    except Exception as e:
        print(f"获取账户现金失败: {e}")
        return None


def get_current_price(ib, symbol):
    """获取股票实时价格（备用）"""
    try:
        contract = Stock(symbol, 'SMART', 'USD')
        ticker = ib.reqMktData(contract, '', False, False)
        ib.sleep(1)
        price = ticker.last if ticker.last else (ticker.bid if ticker.bid else ticker.ask)
        return price
    except Exception as e:
        print(f"获取 {symbol} 价格失败: {e}")
        return None


def place_order(ib, symbol, side, quantity, order_type="MARKET", limit_price=None, stop_price=None, dry_run=False):
    """
    下订单
    quantity: 可以是小数（支持碎股）
    """
    if dry_run:
        print(f"[DRY RUN] 订单: {side} {quantity} {symbol} at {order_type}")
        if order_type == "LIMIT" and limit_price:
            print(f"[DRY RUN] 限价: {limit_price}")
        if order_type == "STOP" and stop_price:
            print(f"[DRY RUN] 止损价: {stop_price}")
        return {"order_id": "dry_run", "status": "DryRun", "filled_quantity": 0, "avg_fill_price": 0}

    contract = Stock(symbol, 'SMART', 'USD')

    if order_type == "MARKET":
        order = MarketOrder(side, quantity)
    elif order_type == "LIMIT":
        if limit_price is None:
            raise ValueError("LIMIT order requires limit_price")
        order = LimitOrder(side, quantity, limit_price)
    elif order_type == "STOP":
        if stop_price is None:
            raise ValueError("STOP order requires stop_price")
        order = StopOrder(side, quantity, stop_price)
    else:
        raise ValueError(f"Unsupported order type: {order_type}")

    try:
        trade = ib.placeOrder(contract, order)
        ib.sleep(1)

        commission = 0.001

        if trade.orderStatus.status == 'Filled':
            # 获取佣金（可能需要额外请求）
            # 简化处理：返回估算值或从 trade 对象获取
            commission = trade.orderStatus.commission if hasattr(trade.orderStatus, 'commission') else 0.001

        return {
            "order_id": trade.order.orderId,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "status": trade.orderStatus.status,
            "filled_quantity": trade.orderStatus.filled,
            "avg_fill_price": trade.orderStatus.avgFillPrice,
            "commission": commission
        }
    except Exception as e:
        return {"error": str(e)}


def get_positions(ib):
    """获取当前持仓"""
    positions = ib.positions()
    result = []
    for pos in positions:
        result.append({
            "symbol": pos.contract.symbol,
            "quantity": pos.position,
            "avg_cost": pos.avgCost,
            "market_price": pos.marketPrice(),
            "unrealized_pnl": pos.unrealizedPNL
        })
    return result


def get_account_summary(ib):
    """获取账户摘要"""
    try:
        values = ib.accountValues()
        account_info = {}
        for v in values:
            if v.tag in ['NetLiquidation', 'TotalCashBalance', 'GrossPositionValue']:
                account_info[v.tag] = v.value
        return account_info
    except Exception as e:
        return {"error": str(e)}


def execute_order(args):
    """
    程序化执行订单
    args: Namespace 对象，包含订单参数
    """
    if args.dry_run:
        print(f"[DRY RUN] 订单: {args.side} {args.quantity} {args.symbol} at {args.type}")
        if hasattr(args, 'limit_price') and args.limit_price:
            print(f"[DRY RUN] 限价: {args.limit_price}")
        if hasattr(args, 'stop_price') and args.stop_price:
            print(f"[DRY RUN] 止损价: {args.stop_price}")
        return {
            "order_id": "dry_run",
            "symbol": args.symbol,
            "side": args.side,
            "quantity": args.quantity,
            "order_type": args.type,
            "status": "DryRun",
            "filled_quantity": 0,
            "avg_fill_price": 0
        }

    ib = None
    try:
        ib = connect_ib(args.host, args.port, args.client_id)
        result = place_order(ib, args.symbol, args.side, args.quantity,
                            args.type, args.limit_price, args.stop_price, dry_run=False)
        return result
    except Exception as e:
        return {"error": str(e)}
    finally:
        if ib:
            ib.disconnect()


def main():
    parser = argparse.ArgumentParser(description="IBKR Trading Client")
    parser.add_argument("--connect", action="store_true", help="仅测试连接")
    parser.add_argument("--host", default=None, help="IBKR host")
    parser.add_argument("--port", type=int, default=None, help="IBKR port")
    parser.add_argument("--client-id", type=int, default=None, help="Client ID")
    parser.add_argument("--order", action="store_true", help="Place an order")
    parser.add_argument("--positions", action="store_true", help="Get current positions")
    parser.add_argument("--account", action="store_true", help="Get account summary")
    parser.add_argument("--symbol", help="Stock symbol")
    parser.add_argument("--side", choices=["BUY", "SELL"], help="Order side")
    parser.add_argument("--quantity", type=float, help="Order quantity (supports fractional)")
    parser.add_argument("--type", choices=["MARKET", "LIMIT", "STOP"], default="MARKET", help="Order type")
    parser.add_argument("--limit-price", type=float, help="Limit price for LIMIT orders")
    parser.add_argument("--stop-price", type=float, help="Stop price for STOP orders")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (no actual orders)")
    parser.add_argument("--disconnect", action="store_true", help="Disconnect after operation")

    args = parser.parse_args()

    # 如果只是 dry-run 且没有实际需要连接的操作
    if args.dry_run and not args.connect and not args.positions and not args.account and not args.order:
        print("[DRY RUN] 模拟模式，无操作")
        return

    ib = None
    need_connection = args.connect or args.order or args.positions or args.account

    try:
        if need_connection and not args.dry_run:
            ib = connect_ib(args.host, args.port, args.client_id)
        elif need_connection and args.dry_run:
            print("[DRY RUN] 模拟模式，跳过实际连接")

        if args.positions:
            if ib:
                pos = get_positions(ib)
                print(json.dumps(pos, indent=2))
            else:
                print("[DRY RUN] 模拟持仓: []")

        elif args.account:
            if ib:
                acc = get_account_summary(ib)
                print(json.dumps(acc, indent=2))
            else:
                print("[DRY RUN] 模拟账户: 净清算价值=100000, 现金=100000")

        elif args.order:
            if not args.symbol or not args.side or not args.quantity:
                print(json.dumps({"error": "Missing required parameters for order"}))
                sys.exit(1)
            result = execute_order(args)
            print(json.dumps(result, indent=2))

        elif args.connect:
            if ib:
                print(json.dumps({"message": "Connected to IBKR"}, indent=2))
            else:
                print("[DRY RUN] 模拟连接成功")

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    finally:
        if ib and (args.disconnect or args.order or args.positions or args.account):
            ib.disconnect()
            print("已断开连接")


if __name__ == "__main__":
    main()