#!/usr/bin/env python3
# scripts/config.py
import os
import yaml
from pathlib import Path

# ----------------------------- 路径定位 -----------------------------
# 当前文件: scripts/core/config.py
SCRIPT_DIR = Path(__file__).parent                    # scripts/core/
SCRIPTS_DIR = SCRIPT_DIR.parent                       # scripts/
SKILL_ROOT = SCRIPTS_DIR.parent                       # skills/quant-trade/
PROJECT_ROOT = SKILL_ROOT.parent.parent               # quant-trade/（项目根）

# ----------------------------- 数据目录 -----------------------------
# 优先使用环境变量，否则使用项目内 data/quant_trade
DATA_ROOT = Path(os.getenv('QUANT_DATA_ROOT', PROJECT_ROOT / 'data' / 'quant_trade'))

DB_PATH = DATA_ROOT / "db" / "market_data.db"
LOG_DIR = DATA_ROOT / "logs"
CACHE_DIR = DATA_ROOT / "cache"
BACKTEST_DIR = DATA_ROOT / "backtest"
TIKERS_DIR = DATA_ROOT / "tickers"
WAREHOUSE_DIR = DATA_ROOT / "warehouse"

# 确保目录存在
DATA_ROOT.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
TIKERS_DIR.mkdir(parents=True, exist_ok=True)
WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------- 配置文件 -----------------------------
CONFIG_FILE = SKILL_ROOT / "config.yaml"

# 默认配置（硬编码）
DEFAULTS = {
    'risk': {
        'max_order_value': 10000,
        'max_order_shares': 500,
        'daily_loss_limit': 2000,
        'max_position_pct': 20,
        'max_open_positions': 10,
        'stop_loss_pct': -8,
        'take_profit_pct': 25,
        'trailing_stop_pct': 10,
        'max_hold_days': 20,
        'min_hold_days': 3,
    },
    'screener': {
        'rps_threshold': 85,
        'rps_periods': [20, 60, 120],
        'max_buy': 3,
        'max_own': 5,
        'use_fundamentals': False,
    },
    'ibkr': {
        'host': '127.0.0.1',
        'port': 7497,
        'client_id': 1,
        'timeout': 30,
    },
    'data_source': 'yfinance',
    'polygon_api_key': '',
    'commission': 0.001,
}

def deep_merge(base, override):
    """递归合并字典"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result

# 加载 YAML 配置（如果存在）
if CONFIG_FILE.exists():
    with open(CONFIG_FILE) as f:
        user_config = yaml.safe_load(f)
    config = deep_merge(DEFAULTS, user_config)
else:
    config = DEFAULTS

# ----------------------------- 暴露模块级常量 -----------------------------
# 风险参数
MAX_ORDER_VALUE = config['risk']['max_order_value']
MAX_ORDER_SHARES = config['risk']['max_order_shares']
DAILY_LOSS_LIMIT = config['risk']['daily_loss_limit']
MAX_POSITION_PCT = config['risk']['max_position_pct']
MAX_OPEN_POSITIONS = config['risk']['max_open_positions']
STOP_LOSS_PCT = config['risk']['stop_loss_pct']
TAKE_PROFIT_PCT = config['risk']['take_profit_pct']
TRAILING_STOP_PCT = config['risk']['trailing_stop_pct']
MAX_HOLD_DAYS = config['risk']['max_hold_days']
MIN_HOLD_DAYS = config['risk']['min_hold_days']

# 选股参数
RPS_THRESHOLD = config['screener']['rps_threshold']
RPS_PERIODS = config['screener']['rps_periods']
MAX_BUY = config['screener']['max_buy']
MAX_OWN = config['screener']['max_own']
USE_FUNDAMENTALS = config['screener']['use_fundamentals']

# IBKR 参数
IBKR_HOST = config['ibkr']['host']
IBKR_PORT = config['ibkr']['port']
IBKR_CLIENT_ID = config['ibkr']['client_id']
IBKR_TIMEOUT = config['ibkr']['timeout']

# 其他
DATA_SOURCE = config.get('data_source', 'yfinance')
POLYGON_API_KEY = config.get('polygon_api_key', '') or os.getenv('POLYGON_API_KEY', '')
COMMISSION = config.get('commission', 0.001)

__all__ = [
    'DATA_ROOT', 'DB_PATH', 'LOG_DIR', 'CACHE_DIR', 'BACKTEST_DIR',
    'MAX_ORDER_VALUE', 'MAX_ORDER_SHARES', 'DAILY_LOSS_LIMIT',
    'MAX_POSITION_PCT', 'MAX_OPEN_POSITIONS',
    'STOP_LOSS_PCT', 'TAKE_PROFIT_PCT', 'TRAILING_STOP_PCT',
    'MAX_HOLD_DAYS', 'MIN_HOLD_DAYS',
    'RPS_THRESHOLD', 'RPS_PERIODS', 'MAX_BUY', 'MAX_OWN', 'USE_FUNDAMENTALS',
    'IBKR_HOST', 'IBKR_PORT', 'IBKR_CLIENT_ID', 'IBKR_TIMEOUT',
    'DATA_SOURCE', 'POLYGON_API_KEY', 'COMMISSION'
]