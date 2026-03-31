#!/usr/bin/env python3
# scripts/config.py
import os
import yaml
from pathlib import Path

# ----------------------------- 路径定位 -----------------------------
# 当前文件所在目录: .../skills/talon-trade/scripts
SCRIPT_DIR = Path(__file__).parent
# Skill 根目录: .../skills/talon-trade
SKILL_ROOT = SCRIPT_DIR.parent
# 项目根目录（独立 GitHub 项目根）: .../talon-trade
PROJECT_ROOT = SKILL_ROOT.parent.parent

# ----------------------------- 数据目录 -----------------------------
# 优先使用环境变量，否则使用项目内 data/talon_trade
DATA_ROOT = Path(os.getenv('TALON_DATA_ROOT', PROJECT_ROOT / 'data' / 'talon_trade'))
DB_PATH = DATA_ROOT / "market_data.db"
LOG_DIR = DATA_ROOT / "logs"

# 确保目录存在
DATA_ROOT.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

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
        'stop_loss_pct': -8,          # 固定止损百分比（负值）
        'take_profit_pct': 20,        # 固定止盈百分比
        'trailing_stop_pct': 5,       # 移动止损回撤百分比（新增）
        'max_hold_days': 20,          # 最大持有天数（新增）
        'min_hold_days': 3,           # 最小持有天数（新增）
    },
    'screener': {
        'rps_threshold': 90,
        'rps_periods': [20, 60, 120, 250],
        'max_buy': 5,                # 每次买入的最大股票数量（新增）
        'use_fundamentals': False,  # 是否在选股中使用基本面数据（新增）
    },
    'data_source': 'yfinance',
    'polygon_api_key': '',
}

def deep_merge(base, override):
    """递归合并字典，返回新字典"""
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
TRAILING_STOP_PCT = config['risk']['trailing_stop_pct']    # 新增
MAX_HOLD_DAYS = config['risk']['max_hold_days']            # 新增
MIN_HOLD_DAYS = config['risk']['min_hold_days']            # 新增

# 选股参数
RPS_THRESHOLD = config['screener']['rps_threshold']
RPS_PERIODS = config['screener']['rps_periods']
MAX_BUY = config['screener']['max_buy']                    # 新增
USE_FUNDAMENTALS = config['screener']['use_fundamentals']

# 数据源
DATA_SOURCE = config.get('data_source', 'yfinance')
POLYGON_API_KEY = config.get('polygon_api_key', '') or os.getenv('POLYGON_API_KEY', '')

# 可选：导出路径常量（供其他模块使用）
__all__ = [
    'DATA_ROOT', 'DB_PATH', 'LOG_DIR',
    'MAX_ORDER_VALUE', 'MAX_ORDER_SHARES', 'DAILY_LOSS_LIMIT',
    'MAX_POSITION_PCT', 'MAX_OPEN_POSITIONS',
    'STOP_LOSS_PCT', 'TAKE_PROFIT_PCT', 'TRAILING_STOP_PCT',
    'MAX_HOLD_DAYS', 'MIN_HOLD_DAYS',
    'RPS_THRESHOLD', 'RPS_PERIODS', 'HOLD_DAYS',
    'DATA_SOURCE', 'POLYGON_API_KEY', 'MAX_BUY', 'USE_FUNDAMENTALS'
]