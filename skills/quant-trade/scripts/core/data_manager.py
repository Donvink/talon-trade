#!/usr/bin/env python3
"""
数据管理器：本地SQLite存储，支持全量下载和每日增量更新
数据源：yfinance 或 polygon.io
保存所有字段：open, high, low, close, adj_close, volume, dividends, split_ratio
"""

import json
import sqlite3
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timedelta
from pathlib import Path
from core.config import DB_PATH, DATA_SOURCE, POLYGON_API_KEY, WAREHOUSE_DIR

class DataManager:
    def __init__(self):
        self.db_path = DB_PATH
        self.conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self):
        """初始化数据库表，包含所有字段"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS daily (
                symbol TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                adj_close REAL,
                volume INTEGER,
                dividends REAL,
                split_ratio REAL,
                PRIMARY KEY (symbol, date)
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON daily(symbol)")
        # 基本面历史表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS fundamentals_history (
                symbol TEXT,
                date TEXT,               -- 财报发布日或季度截止日
                pe REAL,
                pb REAL,
                roe REAL,                -- 净资产收益率（%）
                market_cap REAL,         -- 市值（亿美元）
                dividend_yield REAL,     -- 股息率（%）
                PRIMARY KEY (symbol, date)
            )
        """)
        self._add_missing_columns()

         # 每日快照表（全市场行情快照）
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_snapshot (
                date TEXT,
                symbol TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                adj_close REAL,
                volume INTEGER,
                PRIMARY KEY (date, symbol)
            )
        """)
        
        # 股票池快照表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pool_snapshot (
                date TEXT,
                pool_type TEXT,
                symbols TEXT,
                metadata TEXT,
                PRIMARY KEY (date, pool_type)
            )
        """)
        
        # 历史市值表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS historical_market_cap (
                symbol TEXT,
                date TEXT,
                market_cap REAL,
                PRIMARY KEY (symbol, date)
            )
        """)
        
        self.conn.commit()

    def _add_missing_columns(self):
        """检查并添加缺失的列（用于升级旧数据库）"""
        cursor = self.conn.execute("PRAGMA table_info(daily)")
        existing_cols = [row[1] for row in cursor.fetchall()]
        needed_cols = ['adj_close', 'dividends', 'split_ratio']
        for col in needed_cols:
            if col not in existing_cols:
                print(f"Adding missing column: {col}")
                self.conn.execute(f"ALTER TABLE daily ADD COLUMN {col} REAL")
        self.conn.commit()

    def get_latest_date(self, symbol: str):
        """获取某只股票本地最新数据日期"""
        cursor = self.conn.execute(
            "SELECT MAX(date) FROM daily WHERE symbol = ?", (symbol,)
        )
        row = cursor.fetchone()
        return row[0] if row[0] else None

    def _fetch_yfinance(self, symbol, start, end):
        """使用yfinance下载数据，保存所有字段"""
        ticker = yf.Ticker(symbol)
        # 下载数据，repair=True 需要 scipy，若未安装可改为 False
        df = ticker.history(start=start, end=end, interval="1d",
                            auto_adjust=False, repair=True)
        if df.empty:
            return pd.DataFrame()
        
        # 保留所有需要的列并重命名
        df = df[['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume', 'Dividends', 'Stock Splits']].copy()
        df.columns = ['open', 'high', 'low', 'close', 'adj_close', 'volume', 'dividends', 'split_ratio']
        
        # 处理时区
        df.index = df.index.tz_localize(None)
        
        # 记录索引的名称（可能是 'Date' 或 None）
        idx_name = df.index.name or 'index'
        # 重置索引，将日期变为普通列
        df.reset_index(inplace=True)
        # 将日期列重命名为 'date'
        df.rename(columns={idx_name: 'date'}, inplace=True)
        
        # 添加股票代码列
        df['symbol'] = symbol
        # 将日期列转换为字符串格式（便于数据库存储）
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')
        
        # 填充股息和拆股的缺失值
        df['dividends'] = df['dividends'].fillna(0.0)
        df['split_ratio'] = df['split_ratio'].fillna(1.0)
        
        # 返回指定顺序的列
        return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'adj_close', 'volume', 'dividends', 'split_ratio']]

    def _fetch_polygon(self, symbol, start, end):
        """使用Polygon.io下载数据（需付费计划）"""
        url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}"
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": POLYGON_API_KEY
        }
        resp = requests.get(url, params=params).json()
        if resp.get('status') != 'OK':
            return pd.DataFrame()
        records = []
        for r in resp.get('results', []):
            records.append({
                'symbol': symbol,
                'date': datetime.fromtimestamp(r['t']/1000).strftime('%Y-%m-%d'),
                'open': r['o'],
                'high': r['h'],
                'low': r['l'],
                'close': r['c'],
                'volume': r['v']
            })
        df = pd.DataFrame(records)
        if df.empty:
            return df
        # 添加缺少的字段（polygon 无股息和拆股信息，adj_close 用 close 代替）
        df['adj_close'] = df['close']
        df['dividends'] = 0.0
        df['split_ratio'] = 1.0
        return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'adj_close', 'volume', 'dividends', 'split_ratio']]

    def download_symbol_range(self, symbol, start, end):
        """下载指定股票、指定日期范围的数据"""
        if DATA_SOURCE == 'yfinance':
            return self._fetch_yfinance(symbol, start, end)
        elif DATA_SOURCE == 'polygon':
            return self._fetch_polygon(symbol, start, end)
        else:
            raise ValueError(f"Unsupported DATA_SOURCE: {DATA_SOURCE}")

    def insert_dataframe(self, df):
        """批量插入数据到数据库，处理重复数据"""
        if df.empty:
            return
        
        # 使用 INSERT OR REPLACE 处理重复
        for _, row in df.iterrows():
            self.conn.execute("""
                INSERT OR REPLACE INTO daily 
                (symbol, date, open, high, low, close, adj_close, volume, dividends, split_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['symbol'], row['date'], row['open'], row['high'], row['low'],
                row['close'], row['adj_close'], row['volume'], row['dividends'], row['split_ratio']
            ))
        self.conn.commit()

    def fetch_and_store(self, symbol, start, end):
        """下载并存储单只股票数据（自动跳过已有数据）"""
        latest = self.get_latest_date(symbol)
        if latest and latest >= end:
            # 已有最新数据
            return
        if latest:
            # 增量下载
            start = (datetime.strptime(latest, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
        df = self.download_symbol_range(symbol, start, end)
        if not df.empty:
            self.insert_dataframe(df)
            print(f"{symbol}: inserted {len(df)} rows")

    def download_full_history(self, symbols, years_back=3):
        """全量下载历史数据"""
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=years_back*365)).strftime('%Y-%m-%d')
        for sym in symbols:
            self.fetch_and_store(sym, start, end)

    def daily_update(self, symbols):
        """每日更新：获取最新交易日数据"""
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
        for sym in symbols:
            self.fetch_and_store(sym, start, end)

    def get_data(self, symbol, start=None, end=None):
        """从本地读取数据，返回DataFrame（索引为date，包含所有字段）"""
        query = "SELECT * FROM daily WHERE symbol = ?"
        params = [symbol]
        if start:
            query += " AND date >= ?"
            params.append(start)
        if end:
            query += " AND date <= ?"
            params.append(end)
        query += " ORDER BY date"
        df = pd.read_sql_query(query, self.conn, params=params)
        if df.empty:
            return df
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        return df
    
    def update_fundamentals(self, symbols, force=False):
        """批量更新基本面数据（从 yfinance 获取）"""
        import yfinance as yf
        for sym in symbols:
            # 检查是否需要更新
            if not force:
                cursor = self.conn.execute(
                    "SELECT update_date FROM fundamentals WHERE symbol = ?", (sym,)
                )
                row = cursor.fetchone()
                if row and (datetime.now() - datetime.fromisoformat(row[0])).days < 7:
                    continue  # 一周内不重复更新
            try:
                ticker = yf.Ticker(sym)
                info = ticker.info
                pe = info.get('trailingPE')
                pb = info.get('priceToBook')
                roe = info.get('returnOnEquity')
                if roe is not None:
                    roe = roe * 100  # 转换为百分比
                market_cap = info.get('marketCap')
                dividend_yield = info.get('dividendYield')
                if dividend_yield is not None:
                    dividend_yield = dividend_yield * 100
                now = datetime.now().isoformat()
                self.conn.execute("""
                    INSERT OR REPLACE INTO fundamentals 
                    (symbol, pe, pb, roe, market_cap, dividend_yield, update_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (sym, pe, pb, roe, market_cap, dividend_yield, now))
                self.conn.commit()
                print(f"Updated fundamentals for {sym}")
            except Exception as e:
                print(f"Failed to update {sym}: {e}")
    
    def get_fundamentals_at_date(self, symbol, as_of_date):
        """获取指定日期之前最新的基本面数据"""
        cursor = self.conn.execute(
            "SELECT pe, pb, roe, market_cap, dividend_yield FROM fundamentals_history "
            "WHERE symbol = ? AND date <= ? ORDER BY date DESC LIMIT 1",
            (symbol, as_of_date)
        )
        row = cursor.fetchone()
        if row:
            return {
                'pe': row[0],
                'pb': row[1],
                'roe': row[2],
                'market_cap': row[3],
                'dividend_yield': row[4]
            }
        return None
    
    def get_all_symbols(self):
        """获取数据库中所有出现过股票代码"""
        cursor = self.conn.execute("SELECT DISTINCT symbol FROM daily")
        return [row[0] for row in cursor.fetchall()]
    
    def save_daily_snapshot(self, date: str, df: pd.DataFrame):
        """保存当日全市场行情快照（Parquet）"""
        file_path = WAREHOUSE_DIR / f"{date}.parquet"
        df.to_parquet(file_path, index=False)
    
    def save_pool_snapshot(self, date: str, pool_type: str, symbols: list, metadata: dict = None):
        """保存股票池快照"""
        conn = self.conn
        conn.execute("""
            INSERT OR REPLACE INTO pool_snapshot (date, pool_type, symbols, metadata)
            VALUES (?, ?, ?, ?)
        """, (date, pool_type, json.dumps(symbols), json.dumps(metadata) if metadata else None))
        conn.commit()
    
    def get_historical_pool(self, date: str, pool_type: str) -> list:
        """获取历史某天的股票池"""
        cursor = self.conn.execute(
            "SELECT symbols FROM pool_snapshot WHERE date <= ? AND pool_type = ? ORDER BY date DESC LIMIT 1",
            (date, pool_type)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None
    
    def get_historical_market_cap(self, symbol: str, date: str) -> float:
        """获取历史某天的市值（需要预先填充历史市值表）"""
        cursor = self.conn.execute(
            "SELECT market_cap FROM historical_market_cap WHERE symbol = ? AND date <= ? ORDER BY date DESC LIMIT 1",
            (symbol, date)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def close(self):
        self.conn.close()