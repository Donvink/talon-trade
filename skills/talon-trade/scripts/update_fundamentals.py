# scripts/update_fundamentals.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from data_manager import DataManager
from stock_pool import get_sp500_symbols

dm = DataManager()
symbols = get_sp500_symbols()
dm.update_fundamentals(symbols, force=True)
dm.close()
print("基本面数据更新完成")