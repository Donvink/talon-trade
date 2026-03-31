#!/usr/bin/env python3
"""
股票池管理：从Wikipedia获取标普500成分股，存入SQLite
"""

import pandas as pd
import sqlite3
import requests
import time
import random
from pathlib import Path
from datetime import datetime
from config import DB_PATH, DATA_ROOT

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
GITHUB_CSV_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
LOCAL_CSV = DATA_ROOT / "sp500_components.csv"  # 本地缓存CSV

HEADERS_LIST = [
    {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'},
    {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15'},
    {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'},
]

def _get_conn():
    """获取数据库连接并确保表存在"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_pool (
            symbol TEXT PRIMARY KEY,
            added_date TEXT
        )
    """)
    conn.commit()
    return conn

def _fetch_from_wikipedia(max_retries=3):
    """从Wikipedia获取成分股，带重试和随机User-Agent"""
    for attempt in range(max_retries):
        headers = random.choice(HEADERS_LIST)
        try:
            resp = requests.get(SP500_URL, headers=headers, timeout=15)
            resp.raise_for_status()
            tables = pd.read_html(resp.text)
            df = tables[0]
            symbols = df['Symbol'].tolist()
            if symbols:
                # 保存到本地CSV
                df.to_csv(LOCAL_CSV, index=False)
                return symbols
        except Exception as e:
            print(f"爬取尝试 {attempt+1} 失败: {e}")
            time.sleep(2 ** attempt)
    return None

def _download_from_github():
    """从GitHub仓库下载成分股CSV（备用数据源）"""
    try:
        print("尝试从 GitHub 下载成分股列表...")
        resp = requests.get(GITHUB_CSV_URL, timeout=15)
        resp.raise_for_status()
        # 保存原始内容到本地CSV
        with open(LOCAL_CSV, 'wb') as f:
            f.write(resp.content)
        # 读取验证
        df = pd.read_csv(LOCAL_CSV)
        if 'Symbol' in df.columns:
            symbols = df['Symbol'].tolist()
            print(f"从 GitHub 成功下载 {len(symbols)} 只股票")
            return symbols
        else:
            print("GitHub CSV 缺少 Symbol 列，忽略")
            return None
    except Exception as e:
        print(f"GitHub 下载失败: {e}")
        return None

def _load_from_local_csv():
    """从本地CSV加载备用列表"""
    if LOCAL_CSV.exists():
        try:
            df = pd.read_csv(LOCAL_CSV)
            if 'Symbol' in df.columns:
                return df['Symbol'].tolist()
            else:
                print("本地 CSV 缺少 Symbol 列")
        except Exception as e:
            print(f"读取本地 CSV 失败: {e}")
    return None

def _get_fallback_symbols():
    """最终备用列表（前20只标普500）"""
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
            "JPM", "V", "JNJ", "WMT", "PG", "UNH", "HD", "DIS", "MA", "BAC",
            "XOM", "CVX"]

def get_sp500_symbols(force_refresh=False):
    """
    获取标普500成分股列表
    - force_refresh=False: 优先从SQLite读取，若无则尝试获取并缓存
    - force_refresh=True:  强制重新从网络获取，并覆盖所有本地缓存
    """
    # 1. 若非强制刷新，优先使用SQLite缓存
    if not force_refresh:
        conn = _get_conn()
        cursor = conn.execute("SELECT symbol FROM stock_pool ORDER BY symbol")
        rows = cursor.fetchall()
        conn.close()
        if rows:
            return [row[0] for row in rows]

    # 2. 强制刷新或无缓存时，从网络获取最新数据
    symbols = None
    # 2.1 先尝试Wikipedia爬取（最及时）
    symbols = _fetch_from_wikipedia()
    # 2.2 若失败，尝试GitHub自动下载（会覆盖本地CSV）
    if symbols is None:
        symbols = _download_from_github()
    # 2.3 若仍失败，尝试本地CSV（但force_refresh时通常不会走这里，除非上面都失败且本地有旧文件）
    if symbols is None and not force_refresh:
        symbols = _load_from_local_csv()
    # 2.4 最后使用硬编码备用列表
    if symbols is None:
        symbols = _get_fallback_symbols()
        print("警告：无法获取最新标普500列表，使用备用列表（前20只）。")

    # 3. 更新数据库（写入最新数据）
    conn = _get_conn()
    conn.execute("DELETE FROM stock_pool")
    now = datetime.now().isoformat()
    for sym in symbols:
        conn.execute("INSERT INTO stock_pool (symbol, added_date) VALUES (?, ?)", (sym, now))
    conn.commit()
    conn.close()
    return symbols