#!/usr/bin/env python3
"""
抓取标普500股票的历史基本面数据（季度频率）
用法: python update_fundamentals_history.py
"""

import sys
import yfinance as yf
import pandas as pd
from pathlib import Path
from datetime import datetime

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from data_manager import DataManager
from stock_pool import get_sp500_symbols

def fetch_fundamentals_for_symbol(symbol):
    """获取单只股票的历史基本面数据，返回 DataFrame"""
    ticker = yf.Ticker(symbol)
    try:
        # 获取季度财务报表
        income = ticker.quarterly_financials
        balance = ticker.quarterly_balance_sheet
        # 获取当前信息（用于补充部分缺失指标）
        info = ticker.info
    except Exception as e:
        print(f"Failed to fetch data for {symbol}: {e}")
        return pd.DataFrame()

    if income.empty or balance.empty:
        print(f"No quarterly data for {symbol}")
        return pd.DataFrame()

    # 合并并计算指标
    # 注意：income 和 balance 的列是日期（季度末），需要对齐
    dates = income.columns.intersection(balance.columns)
    if len(dates) == 0:
        return pd.DataFrame()

    records = []
    for date in dates:
        # 净利润（单位：美元）
        net_income = income.loc['Net Income', date] if 'Net Income' in income.index else None
        # 股东权益（总权益）
        total_equity = balance.loc['Total Equity Gross Minority Interest', date] if 'Total Equity Gross Minority Interest' in balance.index else None
        
        # 计算 ROE = 净利润 / 股东权益 * 100
        if net_income and total_equity and total_equity != 0:
            roe = net_income / total_equity * 100
        else:
            roe = None
        
        # 市盈率：需要知道每股收益和股价，这里用历史快照较复杂，可暂时用当前值
        # 简化：用当季净利润和当前市值估算（不准确），或直接使用当前 PE
        pe = info.get('trailingPE') if date == dates[-1] else None  # 仅最新季度用当前PE
        pb = info.get('priceToBook') if date == dates[-1] else None
        
        records.append({
            'symbol': symbol,
            'date': date.strftime('%Y-%m-%d'),
            'pe': pe,
            'pb': pb,
            'roe': roe,
            'market_cap': info.get('marketCap') / 1e9 if info.get('marketCap') else None,  # 亿美元
            'dividend_yield': info.get('dividendYield') * 100 if info.get('dividendYield') else None
        })
    
    return pd.DataFrame(records)

def main():
    dm = DataManager()
    symbols = get_sp500_symbols()  # 全量，可先测试前10只
    print(f"开始抓取 {len(symbols)} 只股票的基本面历史数据...")

    for sym in symbols:
        print(f"Processing {sym}...")
        df = fetch_fundamentals_for_symbol(sym)
        if not df.empty:
            # 插入或替换数据
            for _, row in df.iterrows():
                dm.conn.execute("""
                    INSERT OR REPLACE INTO fundamentals_history 
                    (symbol, date, pe, pb, roe, market_cap, dividend_yield)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (row['symbol'], row['date'], row['pe'], row['pb'], row['roe'], 
                      row['market_cap'], row['dividend_yield']))
            dm.conn.commit()
            print(f"  Inserted {len(df)} records for {sym}")
        else:
            print(f"  No data for {sym}")

    dm.close()
    print("基本面历史数据抓取完成。")

if __name__ == "__main__":
    main()