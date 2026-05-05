#!/usr/bin/env python3
"""
quant-trade 一键交易主脚本
功能：
- 下载/更新历史数据
- 运行RPS选股
- 执行交易（模拟或实盘）
- 止损监控检查
- 回测复盘（可选）
用法：
    python main.py [--step STEP] [--dry-run] [--force-refresh]
    --step: 可选 all, update, screen, trade, monitor, backtest (默认 all)
    --dry-run: 模拟模式，不实际下单
    --force-refresh: 强制重新下载股票池或历史数据
仓位管理：等权重仓位 + 总持仓上限 + 每日买入限制
"""

import argparse
import sys
import logging
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# SCRIPT_DIR = Path(__file__).parent
# sys.path.insert(0, str(SCRIPT_DIR))

# 设置路径
def setup_path():
    scripts_dir = Path(__file__).parent
    try:
        import core.config
    except ImportError:
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

setup_path()

from core.config import (
    LOG_DIR, RPS_THRESHOLD, RPS_PERIODS, TIKERS_DIR,
    MAX_BUY, MAX_OWN, COMMISSION, ORDER_BY,
    IBKR_HOST, IBKR_PORT, IBKR_CLIENT_ID, CACHE_DIR
)
from core.data_manager import DataManager
from core.stock_pool import get_sp500_symbols, get_large_cap_pool
from core.ticker_fetcher import get_all_tickers
from analysis.screener import main as run_screener
from trading.ibkr_client import execute_order, connect_ib, get_account_cash
from trading.stop_loss_monitor import monitor_and_execute as run_stop_loss
from analysis.backtest import backtest

# 设置日志
log_file = LOG_DIR / f"quant_trade_{datetime.now().strftime('%Y%m%d')}.log"
log_file.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 全局股票池（可配置使用标普500或大市值全市场）
USE_LARGE_CAP = True  # True: 市值>50亿美元全市场, False: 标普500
MIN_MARKET_CAP_BILLION = 5  # 最小市值（十亿美元）


def get_stock_pool(force_refresh=False):
    """获取当前使用的股票池"""
    if USE_LARGE_CAP:
        logger.info(f"使用大市值股票池（市值 > {MIN_MARKET_CAP_BILLION}B）")
        return get_large_cap_pool(min_market_cap_billion=MIN_MARKET_CAP_BILLION, force_refresh=force_refresh)
    else:
        logger.info("使用标普500股票池")
        return get_sp500_symbols(force_refresh=force_refresh)


def download_history(dm, symbols, years_back=2, force=False):
    """下载全量历史数据"""
    logger.info(f"开始下载历史数据（{years_back}年），股票数：{len(symbols)}")
    dm.download_full_history(symbols, years_back=years_back)
    logger.info("历史数据下载完成")


def update_daily(dm, symbols):
    """每日增量更新"""
    logger.info("开始每日增量更新")
    dm.daily_update(symbols)
    logger.info("每日更新完成")

def save_daily_warehouse(dm, symbols, candidates):
    """保存每日数据仓库快照"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 1. 保存全市场行情快照（需要先获取当日所有股票数据）
    all_data = []
    for sym in symbols:
        df = dm.get_data(sym, end=today)
        if not df.empty and df.index[-1].strftime('%Y-%m-%d') == today:
            row = df.iloc[-1].to_dict()
            row['symbol'] = sym
            row['date'] = today
            all_data.append(row)
    if all_data:
        df_snapshot = pd.DataFrame(all_data)
        dm.save_daily_snapshot(today, df_snapshot)
    
    # 2. 保存全市场股票池
    dm.save_pool_snapshot(today, 'all', symbols)
    
    # 3. 保存大市值股票池（如果使用）
    if USE_LARGE_CAP:
        large_cap_symbols = get_stock_pool(force_refresh=False)
        dm.save_pool_snapshot(today, 'large_cap', large_cap_symbols, 
                              metadata={'min_cap_b': MIN_MARKET_CAP_BILLION})
    
    # 4. 保存RPS候选池
    if candidates:
        dm.save_pool_snapshot(today, 'rps_candidates', candidates,
                              metadata={'rps_threshold': RPS_THRESHOLD, 'rps_periods': RPS_PERIODS})

def screen_stocks():
    """运行RPS选股，返回候选列表"""
    logger.info("运行RPS选股...")
    run_screener()
    candidates_file = CACHE_DIR / "rps_candidates.json"
    if not candidates_file.exists():
        logger.warning("未找到选股结果文件，选股可能失败")
        return []
    with open(candidates_file) as f:
        data = json.load(f)
    candidates = data.get('candidates', [])
    logger.info(f"候选股票数量：{len(candidates)}")
    return candidates


def get_current_holdings(ib):
    """获取当前持仓市值"""
    positions = ib.positions()
    holdings = {}
    for pos in positions:
        try:
            price = pos.marketPrice()
        except AttributeError:
            ticker = ib.reqMktData(pos.contract, '', False, False)
            ib.sleep(0.5)
            price = ticker.last if ticker.last else ticker.bid
            if price is None:
                price = pos.avgCost
        holdings[pos.contract.symbol] = pos.position * price
    return holdings


def execute_trades(candidates, dry_run=False):
    """
    执行交易：等权重仓位管理
    - 每只股票目标市值 = 账户总资产 / max_own
    - 每日最多买入 max_buy 只新股票
    - 现金不足时按比例分配
    """
    if not candidates:
        logger.info("无候选股票，跳过交易")
        return

    if not dry_run:
        ib = connect_ib(host=IBKR_HOST, port=IBKR_PORT, client_id=IBKR_CLIENT_ID)
        # 获取净值
        net_liquidation = None
        for v in ib.accountValues():
            if v.tag == 'NetLiquidation':
                net_liquidation = float(v.value)
                break
        # 获取现金
        cash = None
        for v in ib.accountValues():
            if v.tag == 'TotalCashBalance':
                cash = float(v.value)
                break
        # 获取当前持仓
        current_holdings = get_current_holdings(ib)
        ib.disconnect()
    else:
        net_liquidation = 100000
        cash = 100000
        current_holdings = {}

    # 检查持仓数量限制
    current_holdings_count = len(current_holdings)
    if current_holdings_count >= MAX_OWN:
        logger.info(f"当前持仓已达上限 ({current_holdings_count}/{MAX_OWN})，不再买入新股票")
        return

    available_slots = MAX_OWN - current_holdings_count
    logger.info(f"当前持仓: {current_holdings_count}/{MAX_OWN}, 还可买入 {available_slots} 只")

    if net_liquidation is None:
        net_liquidation = 100000
        logger.warning("无法获取净值，使用默认值 $100,000")
    if cash is None:
        cash = 100000
        logger.warning("无法获取现金，使用默认值 $100,000")

    # 计算目标每只股票市值
    target_per_stock = net_liquidation / MAX_OWN
    logger.info(f"账户总资产: ${net_liquidation:,.2f}, 最大持仓: {MAX_OWN}, 目标市值/股: ${target_per_stock:.2f}")

    # 筛选未持仓的候选，并限制数量
    candidates_to_buy = [sym for sym in candidates if sym not in current_holdings]
    candidates_to_buy = candidates_to_buy[:min(MAX_BUY, available_slots)]

    if not candidates_to_buy:
        logger.info("所有候选股票已在持仓中或已达买入上限")
        return

    buy_needed = {}
    for sym in candidates_to_buy:
        current_value = current_holdings.get(sym, 0)
        needed = target_per_stock - current_value
        if needed > 0:
            buy_needed[sym] = needed
        else:
            logger.info(f"{sym} 已达到目标市值，无需买入")

    if not buy_needed:
        return

    total_needed = sum(buy_needed.values())
    if total_needed > cash:
        ratio = cash / total_needed
        logger.info(f"现金不足，按 {ratio:.2%} 比例分配")
        buy_amounts = {sym: needed * ratio for sym, needed in buy_needed.items()}
    else:
        buy_amounts = buy_needed

    # 获取本地价格并下单
    dm = DataManager()
    for sym, amount in buy_amounts.items():
        try:
            df = dm.get_data(sym)
            if df.empty:
                logger.warning(f"{sym} 无本地数据")
                continue
            current_price = df['adj_close'].iloc[-1]
        except Exception as e:
            logger.error(f"获取 {sym} 价格失败: {e}")
            continue

        if current_price is None or current_price <= 0:
            logger.warning(f"{sym} 价格无效")
            continue

        quantity = int(amount / current_price)
        if quantity <= 0:
            logger.warning(f"{sym} 资金不足或价格过高")
            continue

        actual_cost = quantity * current_price
        if actual_cost > cash:
            actual_cost = cash
            quantity = int(cash / current_price)
            if quantity == 0:
                continue

        logger.info(f"买入 {sym} {quantity}股 (约 ${actual_cost:.2f})，目标: ${target_per_stock:.2f}")

        args = argparse.Namespace(
            dry_run=dry_run,
            order=True,
            symbol=sym,
            side="BUY",
            quantity=quantity,
            type="MARKET",
            limit_price=None,
            stop_price=None,
            host=IBKR_HOST,
            port=IBKR_PORT,
            client_id=IBKR_CLIENT_ID,
            connect=False,
            positions=False,
            disconnect=True,
            account=False
        )
        result = execute_order(args)
        if result:
            if 'error' in result:
                logger.error(f"订单失败: {result['error']}")
            else:
                logger.info(f"订单成功: {result}")
                cash -= actual_cost

    dm.close()


def run_backtest():
    """运行回测复盘（使用当前股票池）"""
    logger.info("开始回测复盘...")
    symbols = get_sp500_symbols(force_refresh=False)
    # symbols = get_stock_pool(force_refresh=False)
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    initial_capital = 100000
    trades_df, final_value = backtest(
        stock_pool=symbols,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        order_by=ORDER_BY,
    )
    logger.info(f"回测完成，初始资金: ${initial_capital:,.2f}，最终资产：${final_value:,.2f}")


def main():
    parser = argparse.ArgumentParser(description="Quant-Trade 一键交易流程")
    parser.add_argument("--step", choices=['all', 'update', 'screen', 'trade', 'monitor', 'backtest'],
                        default='all', help="执行步骤")
    parser.add_argument("--dry-run", action="store_true", help="模拟模式")
    parser.add_argument("--force-refresh", action="store_true", help="强制刷新")
    args = parser.parse_args()

    if args.dry_run and args.step == 'trade':
        logger.info("[DRY RUN] 模拟交易模式")
        cand_file = CACHE_DIR / "latest_candidates.txt"
        if cand_file.exists():
            with open(cand_file) as f:
                candidates = [line.strip() for line in f if line.strip()]
        else:
            candidates = screen_stocks()
        execute_trades(candidates, dry_run=True)
        return

    dm = DataManager()
    # 获取股票池（如果强制刷新则重新获取）
    symbols = get_stock_pool(force_refresh=args.force_refresh)

    try:
        # 数据更新步骤
        if args.step in ('all', 'update'):
            # 先检查并更新全市场股票列表（每周一次）
            ticker_cache_file = TIKERS_DIR / "all_tickers.csv"
            need_update_tickers = False
            if not ticker_cache_file.exists():
                need_update_tickers = True
            else:
                mtime = datetime.fromtimestamp(ticker_cache_file.stat().st_mtime)
                if (datetime.now() - mtime).days >= 7:
                    need_update_tickers = True
            if need_update_tickers:
                logger.info("全市场股票列表已过期，正在更新...")
                get_all_tickers(force_refresh=True)

            # 更新行情数据
            conn = sqlite3.connect(dm.db_path)
            cursor = conn.execute("SELECT COUNT(*) FROM daily")
            count = cursor.fetchone()[0]
            conn.close()
            if count == 0 or args.force_refresh:
                download_history(dm, symbols, years_back=2, force=args.force_refresh)
            else:
                update_daily(dm, symbols)
        else:
            logger.info("跳过数据更新步骤")

        # 选股步骤
        if args.step in ('all', 'screen'):
            candidates = screen_stocks()
            with open(CACHE_DIR / "latest_candidates.txt", 'w') as f:
                f.write('\n'.join(candidates))
            with open(CACHE_DIR / "em_candidates.txt", 'w') as f:
                f.write(','.join(candidates))
            save_daily_warehouse(dm, symbols, candidates)
        else:
            if args.step == 'trade':
                cand_file = CACHE_DIR / "latest_candidates.txt"
                if cand_file.exists():
                    with open(cand_file) as f:
                        candidates = [line.strip() for line in f if line.strip()]
                else:
                    logger.error("未找到候选列表文件，请先运行选股")
                    sys.exit(1)

        # 止损监控
        if args.step in ('all', 'monitor'):
            logger.info("运行止损监控检查")
            run_stop_loss()

        # 交易步骤
        if args.step in ('all', 'trade'):
            if 'candidates' not in locals():
                candidates = []
            try:
                execute_trades(candidates, dry_run=args.dry_run)
            except Exception as e:
                logger.error(f"交易执行失败: {e}，继续执行后续步骤")

        # 回测步骤
        if args.step in ('all', 'backtest'):
            run_backtest()

    except Exception as e:
        logger.exception(f"流程执行失败: {e}")
        sys.exit(1)
    finally:
        dm.close()
        logger.info("quant-trade 流程结束")


if __name__ == "__main__":
    main()