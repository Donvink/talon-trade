#!/usr/bin/env python3
"""
回测模块：基于 RPS 选股策略，支持动态退出
仓位管理：等权重仓位 + 总持仓上限 + 每日买入限制
支持使用历史股票池（消除前视偏差）
"""

import sys
import json
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
from core.stock_pool import get_sp500_symbols, get_large_cap_pool
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
    return_daily_nav=False,
    use_historical_pool=False,        # 是否使用历史股票池
    historical_pool_type='large_cap'  # 历史池类型: 'large_cap', 'all'
):
    """
    回测 RPS 选股策略（等权重仓位管理）

    参数:
        stock_pool: list, 静态股票代码列表（当 use_historical_pool=False 时使用）
        start_date: str, 回测起始日期 'YYYY-MM-DD'
        end_date: str, 回测结束日期 'YYYY-MM-DD'
        initial_capital: float, 初始资金
        ... 其他参数 ...
        use_historical_pool: bool, 是否使用历史股票池（消除前视偏差）
        historical_pool_type: str, 历史池类型，如 'large_cap', 'all'
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

    # 预加载所有股票数据（从数据库获取全量，避免重复读库）
    print("正在加载全量股票数据...")
    all_symbols = dm.get_all_symbols()  # 需要 DataManager 实现该方法
    if not all_symbols:
        all_symbols = stock_pool  # 降级
    stock_data = {}
    for sym in all_symbols:
        df = dm.get_data(sym, start=start_date, end=end_date)
        if len(df) >= max(rps_periods):
            stock_data[sym] = df
    if not stock_data:
        raise ValueError("No stock data available for the given period.")

    # 辅助函数：获取指定日期的股票池
    def get_daily_pool(date):
        if use_historical_pool:
            pool = dm.get_historical_pool(date.strftime('%Y-%m-%d'), historical_pool_type)
            if pool is not None:
                # 只保留在 stock_data 中存在的股票
                return [sym for sym in pool if sym in stock_data]
            else:
                # 降级：使用静态池
                print(f"警告: {date.date()} 无历史池，使用静态池")
                return [sym for sym in stock_pool if sym in stock_data]
        else:
            return [sym for sym in stock_pool if sym in stock_data]

    progress = tqdm(date_range, desc="回测进度") if 'tqdm' in sys.modules else date_range

    for current_date in progress:
        # 获取当日有效的股票池
        active_pool = get_daily_pool(current_date)
        if not active_pool:
            continue

        # 1. 计算当日有效股票池的 RPS 和评分
        returns_dict = {}
        for sym in active_pool:
            df = stock_data[sym]
            df_cut = df[df.index <= current_date]
            if len(df_cut) < max(rps_periods):
                continue
            ret = calc_returns(df_cut)
            returns_dict[sym] = ret

        scores = {}
        if returns_dict:
            rps_all = calc_rps_for_all(returns_dict)
            for sym in active_pool:
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
    # 示例：使用静态标普500池（默认）
    symbols = get_sp500_symbols()
    # 若要使用历史大市值池（需要先保存每日快照），可调用：
    # trades, final = backtest(symbols, start, end, use_historical_pool=True, historical_pool_type='large_cap')
    start = "2024-01-01"
    end = "2026-03-30"
    trades, final = backtest(symbols, start, end, initial_capital=100000)
    print("\n回测完成。")