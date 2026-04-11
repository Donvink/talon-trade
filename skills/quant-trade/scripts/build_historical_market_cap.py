#!/usr/bin/env python3
"""
构建历史市值表 —— Bug修复版
修复：
  1. [Bug1] ticker列表含NaN导致 yf.download() 崩溃 → 下载前过滤
  2. [Bug2] close_df.index 与 shares_df.index 时区不一致导致乘积全NaN → 统一tz_localize(None)
  3. [Bug3] stack().reset_index() 列名依赖位置顺序，rename时顺序写死不安全 → 用future_stack + 显式rename
"""

import yfinance as yf
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import argparse

from core.data_manager import DataManager
from core.ticker_fetcher import get_large_cap_tickers


# ──────────────────────────────────────────────────────────────────
# Step 1: 批量下载收盘价
# ──────────────────────────────────────────────────────────────────
def download_close_prices(
    symbols: list[str],
    start_date: str,
    end_date: str,
    cache_path: Path = Path("cache/close_prices.parquet"),
    batch_size: int = 500,
) -> pd.DataFrame:
    cache_path.parent.mkdir(exist_ok=True)

    # ★ Bug1 Fix：过滤掉NaN和非字符串，避免 yf.download() 崩溃
    symbols = [s for s in symbols if isinstance(s, str) and s.strip()]

    if cache_path.exists():
        cached = pd.read_parquet(cache_path)
        # ★ Bug2 Fix：读取缓存后立即统一去时区
        if cached.index.tz is not None:
            cached.index = cached.index.tz_localize(None)
        cached_syms = set(cached.columns)
        missing = [s for s in symbols if s not in cached_syms]
        if not missing:
            print(f"价格数据全部命中缓存 ({len(symbols)} 只)")
            return cached.loc[start_date:end_date, symbols]
        print(f"缓存缺少 {len(missing)} 只，增量下载...")
        symbols_to_fetch = missing
    else:
        cached = pd.DataFrame()
        symbols_to_fetch = symbols

    all_batches = []
    n_batches = -(-len(symbols_to_fetch) // batch_size)  # ceil除法
    for i in range(0, len(symbols_to_fetch), batch_size):
        batch = symbols_to_fetch[i : i + batch_size]
        # ★ Bug1 Fix：每批也再过滤一次（防御性）
        batch = [s for s in batch if isinstance(s, str) and s.strip()]
        if not batch:
            continue
        print(f"下载批次 {i//batch_size + 1}/{n_batches}: {len(batch)} 只")
        try:
            raw = yf.download(
                batch,
                start=start_date,
                end=end_date,
                auto_adjust=True,
                progress=False,
                threads=True,
                group_by="ticker",
            )
            if raw.empty:
                print(f"  批次返回空数据，跳过")
                continue

            if len(batch) == 1:
                close = raw[["Close"]].rename(columns={"Close": batch[0]})
            else:
                # 多ticker时 columns 是 MultiIndex (field, ticker)
                close = raw.xs("Close", axis=1, level=1)

            # ★ Bug2 Fix：下载后立即去时区，统一为 tz-naive
            if close.index.tz is not None:
                close.index = close.index.tz_localize(None)

            all_batches.append(close)
        except Exception as e:
            print(f"  批次下载失败: {e}")

    if not all_batches:
        return cached

    new_data = pd.concat(all_batches, axis=1)

    if not cached.empty:
        result = pd.concat([cached, new_data], axis=1)
        # 去除重复列（增量下载时可能出现）
        result = result.loc[:, ~result.columns.duplicated()]
    else:
        result = new_data

    result.to_parquet(cache_path)

    valid_cols = [s for s in symbols if s in result.columns]
    return result.loc[start_date:end_date, valid_cols]


# ──────────────────────────────────────────────────────────────────
# Step 2: 获取历史流通股数（含splits还原）
# ──────────────────────────────────────────────────────────────────
def get_shares_series(symbol: str, dates: pd.DatetimeIndex) -> pd.Series:
    """
    用splits记录从当前股本反推历史股本，消除前视偏差。
    dates 必须是 tz-naive（调用方保证）。
    """
    try:
        ticker = yf.Ticker(symbol)
        current_shares = ticker.info.get("sharesOutstanding", 0)
        if not current_shares:
            return pd.Series(np.nan, index=dates)

        splits = ticker.splits
        if splits.empty:
            return pd.Series(float(current_shares), index=dates)

        shares_series = pd.Series(float(current_shares), index=dates)
        splits_sorted = splits.sort_index(ascending=False)

        for split_date, ratio in splits_sorted.items():
            if ratio <= 0:
                continue
            # ★ Bug2 Fix：splits日期统一去时区再比较
            if hasattr(split_date, 'tzinfo') and split_date.tzinfo is not None:
                split_date = split_date.tz_localize(None)
            mask = dates < split_date
            shares_series[mask] /= ratio

        return shares_series
    except Exception:
        return pd.Series(np.nan, index=dates)


def batch_get_shares(
    symbols: list[str],
    dates: pd.DatetimeIndex,
    max_workers: int = 20,
    cache_path: Path = Path("cache/shares.parquet"),
) -> pd.DataFrame:
    cache_path.parent.mkdir(exist_ok=True)

    # ★ Bug2 Fix：传入前确保dates是tz-naive
    if dates.tz is not None:
        dates = dates.tz_localize(None)

    if cache_path.exists():
        cached = pd.read_parquet(cache_path)
        if cached.index.tz is not None:
            cached.index = cached.index.tz_localize(None)
        missing = [s for s in symbols if s not in cached.columns]
        if not missing:
            print("股本数据全部命中缓存")
            return cached.reindex(index=dates, columns=symbols)
        symbols_to_fetch = missing
        print(f"股本缓存缺少 {len(missing)} 只，补充获取...")
    else:
        cached = pd.DataFrame()
        symbols_to_fetch = symbols

    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(get_shares_series, sym, dates): sym
            for sym in symbols_to_fetch
        }
        for future in tqdm(as_completed(futures), total=len(symbols_to_fetch), desc="获取股本"):
            sym = futures[future]
            try:
                results[sym] = future.result()
            except Exception:
                results[sym] = pd.Series(np.nan, index=dates)

    new_df = pd.DataFrame(results, index=dates)

    result = pd.concat([cached, new_df], axis=1) if not cached.empty else new_df
    result = result.loc[:, ~result.columns.duplicated()]
    result.to_parquet(cache_path)
    return result.reindex(index=dates, columns=symbols)


# ──────────────────────────────────────────────────────────────────
# Step 3: 批量写入数据库
# ──────────────────────────────────────────────────────────────────
def write_to_db(market_cap_df: pd.DataFrame, db: DataManager):
    # ★ Bug3 Fix：不依赖reset_index()后的列位置，用stack()+显式rename
    long = (
        market_cap_df
        .stack(future_stack=True)           # future_stack=True 行为更稳定
        .rename("market_cap")
        .reset_index()
        .rename(columns={"level_0": "date", "level_1": "symbol"})  # 显式指定
        .dropna(subset=["market_cap"])
        .query("market_cap > 0")
    )
    long["date"] = pd.to_datetime(long["date"]).dt.strftime("%Y-%m-%d")

    # (symbol, date, market_cap) 对应SQL占位符顺序
    records = [
        (row.symbol, row.date, row.market_cap)
        for row in long.itertuples(index=False)
    ]

    print(f"写入 {len(records):,} 条记录...")
    db.conn.executemany(
        "INSERT OR REPLACE INTO historical_market_cap (symbol, date, market_cap) VALUES (?, ?, ?)",
        records,
    )
    db.conn.commit()
    print("写入完成")


# ──────────────────────────────────────────────────────────────────
# 诊断函数：帮助排查数据问题
# ──────────────────────────────────────────────────────────────────
def diagnose(close_df: pd.DataFrame, shares_df: pd.DataFrame):
    print("\n===== 诊断信息 =====")
    print(f"close_df:  shape={close_df.shape}, index.tz={close_df.index.tz}, dtype样例={close_df.dtypes.iloc[0]}")
    print(f"shares_df: shape={shares_df.shape}, index.tz={shares_df.index.tz}, dtype样例={shares_df.dtypes.iloc[0]}")

    common_cols = close_df.columns.intersection(shares_df.columns)
    print(f"共同列数: {len(common_cols)} (close有{len(close_df.columns)}, shares有{len(shares_df.columns)})")

    # 抽查前3只的乘积
    for sym in list(common_cols[:3]):
        c = close_df[sym].dropna()
        s = shares_df[sym].dropna()
        product = (c * s).dropna()
        print(f"  {sym}: close非空{len(c)}行, shares非空{len(s)}行, 乘积非空{len(product)}行, 样例={product.iloc[0] if len(product) else 'N/A'}")
    print("===================\n")


# ──────────────────────────────────────────────────────────────────
# 主函数
# ──────────────────────────────────────────────────────────────────
def download_historical_market_cap(
    start_date: str,
    end_date: str,
    use_large_cap_only: bool = False,
    max_workers: int = 20,
    debug: bool = False,
):
    if use_large_cap_only:
        symbols = get_large_cap_tickers(min_market_cap_billion=5, force_refresh=False)
    else:
        from core.ticker_fetcher import get_all_tickers
        symbols = get_all_tickers()

    # ★ Bug1 Fix：主入口处统一过滤
    symbols = [s for s in symbols if isinstance(s, str) and s.strip()]
    print(f"股票池（过滤后）: {len(symbols)} 只")

    close_df = download_close_prices(symbols, start_date, end_date)
    valid_symbols = close_df.columns.tolist()
    dates = close_df.index

    # ★ Bug2 Fix：确保dates tz-naive后再传入
    if dates.tz is not None:
        dates = dates.tz_localize(None)
        close_df.index = dates

    print(f"有效价格数据: {len(valid_symbols)} 只，{len(dates)} 个交易日")

    shares_df = batch_get_shares(valid_symbols, dates, max_workers=max_workers)

    if debug:
        diagnose(close_df, shares_df)

    market_cap_df = close_df * shares_df
    non_null = market_cap_df.notna().sum().sum()
    print(f"市值矩阵: {market_cap_df.shape}，非空值: {non_null:,}")

    if non_null == 0:
        print("⚠️  市值矩阵全空！运行 --debug 查看诊断信息")
        return

    dm = DataManager()
    write_to_db(market_cap_df, dm)
    dm.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="构建历史市值表")
    parser.add_argument("--start", default="2024-01-01", help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end", default=datetime.now().strftime('%Y-%m-%d'), help="结束日期 YYYY-MM-DD")
    parser.add_argument("--large-cap", action="store_true", help="处理大市值股票（默认处理全市场股票）")
    parser.add_argument("--workers", type=int, default=5, help="并发线程数")
    parser.add_argument("--debug", action="store_true", help="打印诊断信息")
    args = parser.parse_args()

    download_historical_market_cap(
        start_date=args.start,
        end_date=args.end,
        use_large_cap_only=args.large_cap,
        max_workers=args.workers,
        debug=args.debug,
    )