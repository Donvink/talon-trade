#!/usr/bin/env python3
"""
生成回测报告：包括月度收益、最大回撤曲线、交易统计等
"""

import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

# 添加 scripts 目录到路径（允许直接运行）
def setup_path():
    # 当前文件: scripts/analysis/generate_report.py
    # scripts 目录: 向上两级
    scripts_dir = Path(__file__).parent.parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

setup_path()

from analysis.backtest import backtest
from core.stock_pool import get_sp500_symbols, get_large_cap_pool
from core.config import LOG_DIR

def calculate_daily_returns(nav_series):
    """计算日收益率序列"""
    return nav_series.pct_change().dropna()

def calculate_monthly_returns(nav_series):
    """计算月度收益率"""
    monthly = nav_series.resample('ME').last()
    monthly_returns = monthly.pct_change().dropna() * 100
    return monthly_returns

def calculate_max_drawdown(nav_series):
    """计算最大回撤"""
    running_max = nav_series.expanding().max()
    drawdown = (nav_series - running_max) / running_max * 100
    max_drawdown = drawdown.min()
    return drawdown, max_drawdown

def plot_equity_curve(nav_series, drawdown_series, start_date, end_date):
    """绘制资产曲线和回撤曲线"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    # 资产曲线
    ax1.plot(nav_series.index, nav_series.values, label='Portfolio Value', color='blue')
    ax1.axhline(y=100000, color='gray', linestyle='--', alpha=0.5, label='Initial Capital')
    ax1.set_ylabel('Portfolio Value ($)')
    ax1.set_title(f'Equity Curve ({start_date} to {end_date})')
    ax1.legend()
    ax1.grid(True)
    
    # 回撤曲线
    ax2.fill_between(drawdown_series.index, drawdown_series.values, 0, color='red', alpha=0.3)
    ax2.plot(drawdown_series.index, drawdown_series.values, color='red', linewidth=0.5)
    ax2.set_ylabel('Drawdown (%)')
    ax2.set_xlabel('Date')
    ax2.set_title('Drawdown Curve')
    ax2.grid(True)
    
    plt.tight_layout()
    plt.savefig(LOG_DIR / 'equity_curve.png', dpi=150)
    plt.show()

def plot_monthly_returns(monthly_returns):
    """绘制月度收益柱状图"""
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ['green' if x > 0 else 'red' for x in monthly_returns.values]
    ax.bar(monthly_returns.index.strftime('%Y-%m'), monthly_returns.values, color=colors)
    ax.axhline(y=0, color='black', linewidth=0.8)
    ax.set_ylabel('Monthly Return (%)')
    ax.set_title('Monthly Returns')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(LOG_DIR / 'monthly_returns.png', dpi=150)
    plt.show()

def main():
    # 回测参数（可根据需要修改）
    # symbols = get_sp500_symbols()
    symbols = get_large_cap_pool()#[:20]
    start_date = "2024-04-01"
    end_date = "2026-03-31"
    initial_capital = 100000
    use_fundamentals = False  # 是否在选股中使用基本面数据

    # 运行回测（需要 backtest 函数返回每日净值序列）
    # 注意：你的 backtest 函数需要修改以返回每日净值列表
    # 这里假设 backtest 已经修改为返回 (trades_df, final_value, daily_nav)
    trades_df, final_value, daily_nav = backtest(
        stock_pool=symbols,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        use_fundamentals=use_fundamentals,
        return_daily_nav=True   # 需要添加此参数
    )

    # 如果 backtest 尚未支持每日净值，可以临时在 backtest 中添加收集逻辑（见下方说明）

    # 转换每日净值为 Series
    nav_series = pd.Series(daily_nav, index=pd.date_range(start=start_date, end=end_date, freq='B'))
    # 实际交易日可能不连续，可以用实际日期索引，这里简化

    # 计算指标
    total_return = (final_value - initial_capital) / initial_capital * 100
    daily_returns = calculate_daily_returns(nav_series)
    sharpe_ratio = daily_returns.mean() / daily_returns.std() * (252 ** 0.5) if daily_returns.std() != 0 else 0
    drawdown_series, max_dd = calculate_max_drawdown(nav_series)
    monthly_returns = calculate_monthly_returns(nav_series)

    # 打印报告
    print("=" * 60)
    print("回测报告")
    print("=" * 60)
    print(f"回测区间: {start_date} 至 {end_date}")
    print(f"初始资金: ${initial_capital:,.2f}")
    print(f"最终资金: ${final_value:,.2f}")
    print(f"总收益率: {total_return:.2f}%")
    print(f"年化收益率: {((1 + total_return/100) ** (252/len(nav_series)) - 1)*100:.2f}%")
    print(f"夏普比率: {sharpe_ratio:.2f}")
    print(f"最大回撤: {max_dd:.2f}%")
    print(f"交易次数: {len(trades_df)}")
    if len(trades_df) > 0:
        win_rate = (trades_df['pnl_pct'] > 0).mean() * 100
        avg_win = trades_df[trades_df['pnl_pct'] > 0]['pnl_pct'].mean()
        avg_loss = trades_df[trades_df['pnl_pct'] < 0]['pnl_pct'].mean()
        print(f"胜率: {win_rate:.2f}%")
        print(f"平均盈利: {avg_win:.2f}%")
        print(f"平均亏损: {avg_loss:.2f}%")
    print("\n月度收益 (%):")
    print(monthly_returns.round(2))
    print("\n")

    # 绘制图表
    plot_equity_curve(nav_series, drawdown_series, start_date, end_date)
    plot_monthly_returns(monthly_returns)

    # 保存交易记录
    trades_df.to_csv(LOG_DIR / 'trades.csv', index=False)
    print(f"交易记录已保存至: {LOG_DIR / 'trades.csv'}")
    print(f"图表已保存至: {LOG_DIR / 'equity_curve.png'} 和 {LOG_DIR / 'monthly_returns.png'}")

if __name__ == "__main__":
    main()