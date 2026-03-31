#!/usr/bin/env python3
"""
talon-trade 一键交易主脚本
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
"""

import argparse
import sys
import logging
import yaml
import pandas as pd
from pathlib import Path
from datetime import datetime

# 添加当前目录到路径（方便导入同目录模块）
sys.path.insert(0, str(Path(__file__).parent))

# 导入项目模块
from config import (
    DATA_ROOT, LOG_DIR, RPS_THRESHOLD, RPS_PERIODS, MAX_BUY,
    DATA_SOURCE, POLYGON_API_KEY, MAX_ORDER_VALUE, MAX_ORDER_SHARES,
    DAILY_LOSS_LIMIT, MAX_POSITION_PCT, MAX_OPEN_POSITIONS,
    STOP_LOSS_PCT, TAKE_PROFIT_PCT
)
from data_manager import DataManager
from stock_pool import get_sp500_symbols
from screener import main as run_screener
from ibkr_client import main as run_ibkr
from risk_checker import main as run_risk
from stop_loss_monitor import monitor_and_execute as run_stop_loss
from backtest import backtest  # 假设 backtest.py 有 backtest 函数

# 设置日志
log_file = LOG_DIR / f"talon_trade_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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

def screen_stocks():
    """运行RPS选股，返回候选列表"""
    logger.info("运行RPS选股...")
    # screener.py 的 main 函数会输出候选并保存 JSON，我们直接调用它
    run_screener()
    # 读取候选结果
    candidates_file = DATA_ROOT / "rps_candidates.json"
    if not candidates_file.exists():
        logger.warning("未找到选股结果文件，选股可能失败")
        return []
    import json
    with open(candidates_file) as f:
        data = json.load(f)
    candidates = data.get('candidates', [])
    logger.info(f"候选股票数量：{len(candidates)}")
    return candidates

def execute_trades(candidates, dry_run=False):
    """执行交易：为每个候选买入固定数量（可配置）"""
    if not candidates:
        logger.info("无候选股票，跳过交易")
        return
    # 默认每个买入10股，可在配置中设定
    quantity = 10  # 可改为从 config 读取
    for sym in candidates:
        logger.info(f"执行交易：买入 {sym} {quantity}股")
        # 构造订单参数
        args = argparse.Namespace(
            dry_run=dry_run,
            order=True,
            symbol=sym,
            side="BUY",
            quantity=quantity,
            type="MARKET",
            limit_price=None,
            stop_price=None,
            host="127.0.0.1",
            port=7497,
            client_id=1,
            connect=False,
            positions=False,
            disconnect=True
        )
        # 调用 ibkr_client 的 main 函数
        run_ibkr(args)  # 注意：ibkr_client的main函数会解析参数，我们需要模拟参数传递

def run_backtest():
    """运行回测复盘"""
    logger.info("开始回测复盘...")
    symbols = get_sp500_symbols()  # 使用全股票池或自定义
    # 回测最近一年
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - pd.Timedelta(days=365)).strftime('%Y-%m-%d')
    trades_df, final_value = backtest(
        stock_pool=symbols,  # 测试用前20只symbols[:20]，实际可全量
        start_date=start_date,
        end_date=end_date,
        initial_capital=100000
    )
    logger.info(f"回测完成，初始资金: $100,000.00，最终资产：{final_value:.2f}")

def main():
    parser = argparse.ArgumentParser(description="Talon-Trade 一键交易流程")
    parser.add_argument("--step", choices=['all', 'update', 'screen', 'trade', 'monitor', 'backtest'],
                        # default='all', help="执行步骤，默认全部")
                        default='backtest', help="执行步骤，默认全部")
    parser.add_argument("--dry-run", action="store_true", help="模拟模式，不实际下单")
    parser.add_argument("--force-refresh", action="store_true", help="强制刷新股票池/历史数据")
    args = parser.parse_args()

    # 初始化数据管理器
    dm = DataManager()
    symbols = get_sp500_symbols(force_refresh=args.force_refresh)

    try:
        if args.step in ('all', 'update'):
            # 检查是否需要全量下载
            # 简单判断：如果数据库为空，则全量下载
            import sqlite3
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

        if args.step in ('all', 'screen'):
            candidates = screen_stocks()
            # 保存候选列表供后续使用
            with open(DATA_ROOT / "latest_candidates.txt", 'w') as f:
                f.write('\n'.join(candidates))
        else:
            # 如果只执行 trade 步骤，需要读取之前的候选
            if args.step == 'trade':
                cand_file = DATA_ROOT / "latest_candidates.txt"
                if cand_file.exists():
                    with open(cand_file) as f:
                        candidates = [line.strip() for line in f if line.strip()]
                else:
                    logger.error("未找到候选列表文件，请先运行选股")
                    sys.exit(1)

        if args.step in ('all', 'trade'):
            if 'candidates' not in locals():
                candidates = []
            execute_trades(candidates, dry_run=args.dry_run)

        if args.step in ('all', 'monitor'):
            logger.info("运行止损监控检查")
            run_stop_loss()  # 此函数会连接IBKR并检查持仓

        if args.step in ('all', 'backtest'):
            run_backtest()

    except Exception as e:
        logger.exception(f"流程执行失败: {e}")
        sys.exit(1)
    finally:
        dm.close()
        logger.info("talon-trade 流程结束")

if __name__ == "__main__":
    main()