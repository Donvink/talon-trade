#!/usr/bin/env python3
"""
回测模块：基于 RPS 选股策略，支持动态退出
仓位管理：等权重仓位 + 总持仓上限 + 每日买入限制
"""

import sys
import pandas as pd
import numpy as np
from datetime import timedelta
from pathlib import Path
from tqdm import tqdm
import pandas_ta as ta
from core.config import (
    RPS_THRESHOLD, RPS_PERIODS,
    STOP_LOSS_PCT, TAKE_PROFIT_PCT, TRAILING_STOP_PCT,
    MAX_HOLD_DAYS, MIN_HOLD_DAYS, MAX_BUY, MAX_OWN, USE_FUNDAMENTALS,
    COMMISSION, LOG_DIR
)
from core.data_manager import DataManager
from core.stock_pool import get_sp500_symbols
from core.rps_calculator import calc_returns, calc_rps_for_all
from core.factors import score_stock


def backtest(
    stock_pool,
    start_date,
    end_date,
    initial_capital=100000,
    rps_threshold=None,
    rps_periods=None,
    stop_loss_pct=None,
    take_profit_pct=None,
    trailing_stop_pct=None,
    max_hold_days=None,
    min_hold_days=None,
    use_macd_sell=True,
    max_buy=None,
    max_own=None,
    commission=None,
    use_fundamentals=None,
    return_daily_nav=False
):
    """
    回测 RPS 选股策略（等权重仓位管理）
    
    参数:
        stock_pool: list, 股票代码列表
        start_date: str, 回测起始日期 'YYYY-MM-DD'
        end_date: str, 回测结束日期 'YYYY-MM-DD'
        initial_capital: float, 初始资金
        rps_threshold: int, RPS 阈值
        rps_periods: list, RPS 周期列表
        stop_loss_pct: float, 固定止损百分比
        take_profit_pct: float, 止盈百分比
        trailing_stop_pct: float, 移动止损回撤百分比
        max_hold_days: int, 最大持有天数
        min_hold_days: int, 最小持有天数
        use_macd_sell: bool, 是否使用 MACD 死叉卖出
        max_buy: int, 每日最多买入数量
        max_own: int, 总持仓上限
        commission: float, 手续费率
        use_fundamentals: bool, 是否使用基本面
        return_daily_nav: bool, 是否返回每日净值
    """
    # 使用配置文件中的默认值
    rps_threshold = rps_threshold if rps_threshold is not None else RPS_THRESHOLD
    rps_periods = rps_periods if rps_periods is not None else RPS_PERIODS
    max_buy = max_buy if max_buy is not None else MAX_BUY
    max_own = max_own if max_own is not None else MAX_OWN
    stop_loss_pct = stop_loss_pct if stop_loss_pct is not None else STOP_LOSS_PCT
    take_profit_pct = take_profit_pct if take_profit_pct is not None else TAKE_PROFIT_PCT
    trailing_stop_pct = trailing_stop_pct if trailing_stop_pct is not None else TRAILING_STOP_PCT
    max_hold_days = max_hold_days if max_hold_days is not None else MAX_HOLD_DAYS
    min_hold_days = min_hold_days if min_hold_days is not None else MIN_HOLD_DAYS
    commission = commission if commission is not None else COMMISSION
    use_fundamentals = use_fundamentals if use_fundamentals is not None else USE_FUNDAMENTALS

    dm = DataManager()
    date_range = pd.date_range(start_date, end_date, freq='B')
    positions = {}      # {symbol: (buy_date, buy_price, shares, buy_score)}
    trades = []
    cash = initial_capital
    portfolio_value = initial_capital
    daily_nav = []

    # 预加载所有股票数据
    stock_data = {}
    for sym in stock_pool:
        df = dm.get_data(sym, start=start_date, end=end_date)
        if len(df) >= max(rps_periods):
            stock_data[sym] = df
    if not stock_data:
        raise ValueError("No stock data available for the given period.")

    progress = tqdm(date_range, desc="回测进度") if 'tqdm' in sys.modules else date_range

    for current_date in progress:
        # 1. 计算当日所有股票的 RPS 和评分
        returns_dict = {}
        for sym, df in stock_data.items():
            df_cut = df[df.index <= current_date]
            if len(df_cut) < max(rps_periods):
                continue
            ret = calc_returns(df_cut)
            returns_dict[sym] = ret

        scores = {}
        if returns_dict:
            rps_all = calc_rps_for_all(returns_dict)
            for sym in stock_pool:
                if sym not in rps_all:
                    continue
                rps_scores = rps_all[sym]
                if all(rps_scores.get(f'{p}d_rps', 0) >= rps_threshold for p in rps_periods):
                    df = stock_data[sym]
                    df_cut = df[df.index <= current_date]
                    if len(df_cut) < max(rps_periods):
                        continue
                    current_date_str = current_date.strftime('%Y-%m-%d')
                    scores[sym] = score_stock(
                        sym, df_cut, rps_scores,
                        as_of_date=current_date_str,
                        use_fundamentals=use_fundamentals
                    )

        # 2. 卖出检查（动态退出）
        for sym, (buy_date, buy_price, shares, buy_score) in list(positions.items()):
            df = stock_data[sym]
            df_cut = df[df.index <= current_date]
            if df_cut.empty:
                continue
            current_price = df_cut['adj_close'].iloc[-1]
            days_held = (current_date - buy_date).days
            pnl_pct = (current_price - buy_price) / buy_price * 100

            high_since_entry = df_cut['adj_close'].loc[buy_date:].max()
            drawdown = (high_since_entry - current_price) / high_since_entry * 100

            sell_reason = None
            if pnl_pct <= stop_loss_pct:
                sell_reason = "stop_loss"
            elif drawdown >= trailing_stop_pct:
                sell_reason = "trailing_stop"
            elif use_macd_sell and days_held >= min_hold_days and len(df_cut) >= 26:
                macd = ta.macd(df_cut['adj_close'], fast=12, slow=26, signal=9)
                if macd is not None and len(macd) > 1:
                    if (macd['MACD_12_26_9'].iloc[-1] < macd['MACDs_12_26_9'].iloc[-1] and
                        macd['MACD_12_26_9'].iloc[-2] >= macd['MACDs_12_26_9'].iloc[-2]):
                        sell_reason = "macd_death_cross"
            elif pnl_pct >= take_profit_pct:
                sell_reason = "take_profit"
            elif days_held >= max_hold_days and pnl_pct < take_profit_pct:
                sell_reason = "time_stop"

            if sell_reason:
                trade_value = shares * current_price
                cash += trade_value * (1 - commission)
                trades.append({
                    'symbol': sym,
                    'buy_date': buy_date,
                    'sell_date': current_date,
                    'buy_price': buy_price,
                    'sell_price': current_price,
                    'pnl_pct': pnl_pct,
                    'pnl_abs': trade_value - shares * buy_price,
                    'sell_reason': sell_reason
                })
                del positions[sym]

        # 3. 买入（等权重仓位管理）
        # 获取当前持仓市值
        current_holdings = {}
        for sym, (buy_date, buy_price, shares, _) in positions.items():
            df = stock_data[sym]
            df_cut = df[df.index <= current_date]
            if not df_cut.empty:
                current_price = df_cut['adj_close'].iloc[-1]
                current_holdings[sym] = shares * current_price

        # 计算账户总资产和目标每只股票市值
        total_asset = cash + sum(current_holdings.values())
        target_per_stock = total_asset / max_own

        # 筛选需要买入的候选（未持仓，且不超过 max_buy）
        candidates_to_buy = []
        for sym, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            if sym not in positions:
                candidates_to_buy.append(sym)
            if len(candidates_to_buy) >= max_buy:
                break

        if candidates_to_buy:
            # 计算每个候选的目标买入金额
            buy_needed = {}
            for sym in candidates_to_buy:
                current_value = current_holdings.get(sym, 0)
                needed = target_per_stock - current_value
                if needed > 0:
                    buy_needed[sym] = needed

            if buy_needed:
                total_needed = sum(buy_needed.values())
                # 现金不足时按比例分配
                if total_needed > cash:
                    ratio = cash / total_needed
                    buy_amounts = {sym: needed * ratio for sym, needed in buy_needed.items()}
                else:
                    buy_amounts = buy_needed

                # 按顺序买入
                for sym, amount in buy_amounts.items():
                    df = stock_data[sym]
                    df_cut = df[df.index <= current_date]
                    if df_cut.empty:
                        continue
                    price = df_cut['adj_close'].iloc[-1]
                    shares = int(amount / price)
                    if shares <= 0:
                        continue
                    actual_cost = shares * price
                    if actual_cost > cash:
                        continue
                    cash -= actual_cost * (1 + commission)
                    positions[sym] = (current_date, price, shares, scores.get(sym, 0))

        # 更新当日总资产
        current_value = cash
        for sym, (_, _, shares, _) in positions.items():
            df = stock_data[sym]
            df_cut = df[df.index <= current_date]
            if not df_cut.empty:
                current_value += shares * df_cut['adj_close'].iloc[-1]
        portfolio_value = current_value
        daily_nav.append(portfolio_value)

    # 强制平仓
    for sym, (buy_date, buy_price, shares, _) in positions.items():
        df = stock_data[sym]
        df_cut = df[df.index <= end_date]
        if not df_cut.empty:
            price = df_cut['adj_close'].iloc[-1]
            trade_value = shares * price
            cash += trade_value * (1 - commission)
            trades.append({
                'symbol': sym,
                'buy_date': buy_date,
                'sell_date': end_date,
                'buy_price': buy_price,
                'sell_price': price,
                'pnl_pct': (price - buy_price) / buy_price * 100,
                'pnl_abs': trade_value - shares * buy_price,
                'sell_reason': 'force_close'
            })

    dm.close()

    # 绩效统计
    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        total_pnl = trades_df['pnl_abs'].sum()
        total_pnl_pct = total_pnl / initial_capital * 100
        win_rate = (trades_df['pnl_pct'] > 0).mean() * 100
        avg_win = trades_df[trades_df['pnl_pct'] > 0]['pnl_pct'].mean() if any(trades_df['pnl_pct'] > 0) else 0
        avg_loss = trades_df[trades_df['pnl_pct'] < 0]['pnl_pct'].mean() if any(trades_df['pnl_pct'] < 0) else 0
        sell_reason_counts = trades_df['sell_reason'].value_counts()
    else:
        total_pnl = 0
        total_pnl_pct = 0
        win_rate = 0
        avg_win = 0
        avg_loss = 0
        sell_reason_counts = pd.Series()

    print(f"回测结果 {start_date} -> {end_date}")
    print(f"初始资金: ${initial_capital:,.2f}")
    print(f"最终资金: ${portfolio_value:,.2f}")
    print(f"总收益: ${total_pnl:,.2f} ({total_pnl_pct:.2f}%)")
    print(f"胜率: {win_rate:.2f}%")
    print(f"平均盈利: {avg_win:.2f}%")
    print(f"平均亏损: {avg_loss:.2f}%")
    print("卖出原因统计:")
    print(sell_reason_counts)

    if return_daily_nav:
        return trades_df, portfolio_value, daily_nav
    else:
        return trades_df, portfolio_value


if __name__ == "__main__":
    symbols = get_sp500_symbols()
    start = "2024-01-01"
    end = "2026-03-30"
    trades, final = backtest(symbols, start, end, initial_capital=100000)
    print("\n回测完成。")