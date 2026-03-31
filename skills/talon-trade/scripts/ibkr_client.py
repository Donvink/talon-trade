#!/usr/bin/env python3
"""
Interactive Brokers 交易客户端（模拟盘）
"""

import argparse
import json
import sys
from ib_insync import IB, Stock, MarketOrder, LimitOrder, StopOrder

def connect_ib(host='127.0.0.1', port=7497, client_id=1):
    ib = IB()
    try:
        ib.connect(host, port, clientId=client_id)
        return ib
    except Exception as e:
        print(json.dumps({"error": f"Failed to connect: {str(e)}"}))
        sys.exit(1)

def place_order(ib, symbol, side, quantity, order_type="MARKET", limit_price=None, stop_price=None):
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
    trade = ib.placeOrder(contract, order)
    ib.sleep(1)
    return trade

def get_positions(ib):
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--connect", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497)
    parser.add_argument("--client-id", type=int, default=1)
    parser.add_argument("--order", action="store_true")
    parser.add_argument("--positions", action="store_true")
    parser.add_argument("--symbol")
    parser.add_argument("--side", choices=["BUY", "SELL"])
    parser.add_argument("--quantity", type=int)
    parser.add_argument("--type", default="MARKET", choices=["MARKET", "LIMIT", "STOP"])
    parser.add_argument("--limit-price", type=float)
    parser.add_argument("--stop-price", type=float)
    parser.add_argument("--disconnect", action="store_true")
    args = parser.parse_args()

    if args.connect or args.order or args.positions:
        ib = connect_ib(args.host, args.port, args.client_id)
    else:
        ib = None

    try:
        if args.positions:
            pos = get_positions(ib)
            print(json.dumps(pos, indent=2))
        elif args.order:
            if not args.symbol or not args.side or not args.quantity:
                print(json.dumps({"error": "Missing required parameters for order"}))
                sys.exit(1)
            trade = place_order(ib, args.symbol, args.side, args.quantity, args.type, args.limit_price, args.stop_price)
            order_status = {
                "order_id": trade.order.orderId,
                "symbol": args.symbol,
                "side": args.side,
                "quantity": args.quantity,
                "order_type": args.type,
                "status": trade.orderStatus.status,
                "filled_quantity": trade.orderStatus.filled,
                "avg_fill_price": trade.orderStatus.avgFillPrice
            }
            print(json.dumps(order_status, indent=2))
        elif args.connect:
            print(json.dumps({"message": "Connected to IBKR"}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
    finally:
        if ib and (args.disconnect or args.order or args.positions):
            ib.disconnect()

if __name__ == "__main__":
    main()