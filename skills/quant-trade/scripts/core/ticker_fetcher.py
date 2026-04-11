#!/usr/bin/env python3
"""
全市场股票代码获取（NYSE + NASDAQ + AMEX）
使用 Nasdaq API 一次性拉取股票列表+市值，无需二次 yfinance 请求
集成到 quant-trade / talon-trade 项目
"""

import os
import pandas as pd
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
from core.config import TIKERS_DIR


def _parse_nasdaq_cap(raw: str) -> float | None:
    """
    解析 Nasdaq API 返回的市值字符串
    格式示例: "2.89T", "345.6B", "12.3M", "$1,234.5B", ""
    """
    if not raw or raw.strip() in ("", "--", "N/A"):
        return None
    s = raw.replace("$", "").replace(",", "").strip().upper()
    multipliers = {"T": 1e12, "B": 1e9, "M": 1e6, "K": 1e3}
    for suffix, mult in multipliers.items():
        if s.endswith(suffix):
            try:
                return float(s[:-1]) * mult
            except ValueError:
                return None
    try:
        return float(s)
    except ValueError:
        return None


def get_large_cap_tickers(
    min_market_cap_billion: float = 10.0,
    force_refresh: bool = False,
    cache_hours: int = 24,
) -> List[str]:
    """
    直接从 Nasdaq Screener API 获取市值 > 阈值的股票代码列表
    无需二次请求 yfinance，速度快且稳定
    """
    cache_file = TIKERS_DIR / f"large_cap_{int(min_market_cap_billion)}b.csv"

    # 检查缓存
    if not force_refresh and cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=cache_hours):
            df = pd.read_csv(cache_file)
            print(f"从缓存加载 {len(df)} 只大市值股票")
            return df["ticker"].tolist()

    min_cap = min_market_cap_billion * 1e9
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nasdaq.com/",
    }

    all_records = []

    for exchange in ["nasdaq", "nyse", "amex"]:
        url = f"https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&exchange={exchange}"
        try:
            r = requests.get(url, headers=headers, timeout=20)
            r.raise_for_status()
            rows = r.json()["data"]["table"]["rows"]
            exchange_records = 0
            for row in rows:
                sym = row.get("symbol", "").strip()
                # 过滤衍生品/优先股：纯字母，长度 1-5
                if not sym.isalpha() or not (1 <= len(sym) <= 5):
                    continue
                cap_raw = row.get("marketCap", "") or ""
                cap = _parse_nasdaq_cap(cap_raw)
                if cap and cap >= min_cap:
                    all_records.append({
                        "ticker": sym,
                        "name": row.get("name", ""),
                        "sector": row.get("sector", ""),
                        "industry": row.get("industry", ""),
                        "exchange": exchange.upper(),
                        "market_cap": cap,
                        "cap_b": round(cap / 1e9, 2),
                        "country": row.get("country", ""),
                    })
                    exchange_records += 1
            print(f"{exchange.upper()}: 筛出 {exchange_records} 只")
        except Exception as e:
            print(f"{exchange} 请求失败: {e}")

    df = (
        pd.DataFrame(all_records)
        .drop_duplicates("ticker")
        .sort_values("market_cap", ascending=False)
        .reset_index(drop=True)
    )
    df.to_csv(cache_file, index=False)
    print(f"\n市值 > ${min_market_cap_billion}B 共 {len(df)} 只")
    return df["ticker"].tolist()


# 可选：如果需要全市场股票列表（不筛选市值），可以保留原 get_all_tickers 或使用类似方法
def get_all_tickers(force_refresh: bool = False, cache_days: int = 7) -> List[str]:
    """获取全市场股票代码（不筛选市值），仅用于特殊需求"""
    # 直接调用 get_large_cap_tickers 并设置极小阈值，或者单独实现
    # 这里简单复用 get_large_cap_tickers 但阈值为 0
    return get_large_cap_tickers(min_market_cap_billion=0, force_refresh=force_refresh)


if __name__ == "__main__":
    # 测试
    df = pd.DataFrame(get_large_cap_tickers(min_market_cap_billion=10.0, force_refresh=True))
    print(df.head(20))