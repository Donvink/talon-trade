---
name: talon-trade
description: US stock quantitative trading system based on RPS (Relative Price Strength) multi-factor selection, supporting backtesting, paper trading, and live trading with Interactive Brokers
version: 1.0.0
metadata:
  openclaw:
    homepage: https://github.com/yourname/talon-trade
    requires:
      anyBins:
        - python3
        - python
---

# 🦞 Talon-Trade

👉 **[GitHub Repository](https://github.com/yourname/talon-trade)**

## Language

**Match user's language**: Respond in the same language the user uses. If the user writes in Chinese, respond in Chinese. If the user writes in English, respond in English.

## Script Directory

**Agent Execution**: This SKILL.md is located at `{baseDir}`, use `{baseDir}/scripts/<name>.py` to execute scripts. Ensure Python 3.10+ is installed and dependencies are configured.

| Script | Purpose |
|--------|---------|
| `{baseDir}/scripts/main.py` | Main execution script, coordinates the entire workflow |
| `{baseDir}/scripts/analysis/backtest.py` | Backtest RPS strategy with dynamic exit rules |
| `{baseDir}/scripts/analysis/screener.py` | RPS stock screening and multi-factor scoring |
| `{baseDir}/scripts/analysis/generate_report.py` | Generate backtest report with equity curve |
| `{baseDir}/scripts/analysis/optimize.py` | Parameter optimization for strategy |
| `{baseDir}/scripts/core/data_manager.py` | Local data management (SQLite, download, incremental update) |
| `{baseDir}/scripts/core/stock_pool.py` | S&P 500 constituent management |
| `{baseDir}/scripts/core/rps_calculator.py` | RPS (Relative Price Strength) calculation |
| `{baseDir}/scripts/core/factors.py` | Multi-factor scoring (volume, fundamentals, etc.) |
| `{baseDir}/scripts/trading/ibkr_client.py` | Interactive Brokers API client (paper/live trading) |
| `{baseDir}/scripts/trading/risk_checker.py` | Risk control and order validation |
| `{baseDir}/scripts/trading/stop_loss_monitor.py` | Stop-loss/take-profit monitoring |
| `{baseDir}/scripts/utils/update_fundamentals.py` | Update fundamental data |

## Configuration Preferences

1. Check config.yaml exists: `{baseDir}/config.yaml`

2. Check .env file exists with API keys: `{baseDir}/.env`

**config.yaml supports**: Risk parameters | Screener parameters | IBKR connection settings | Data source selection | Trading commission
**.env supports**: API keys for data sources (Polygon.io, etc.)

**Minimum supported keys**:

| Key | Default | Description |
|-----|---------|-------------|
| `rps_threshold` | `85` | RPS threshold for stock screening (0-100) |
| `rps_periods` | `[20, 60, 120]` | RPS calculation periods (days) |
| `max_buy` | `3` | Maximum number of stocks to buy per day |
| `max_own` | `5` | Maximum number of stocks to hold |
| `stop_loss_pct` | `-10` | Fixed stop loss percentage |
| `take_profit_pct` | `30` | Take profit percentage |
| `trailing_stop_pct` | `10` | Trailing stop drawdown percentage |
| `max_hold_days` | `25` | Maximum holding days (time stop) |
| `min_hold_days` | `3` | Minimum holding days |
| `use_macd_sell` | `false` | Whether to use MACD death cross as sell signal |
| `use_fundamentals` | `false` | Whether to use fundamental factors (PE/ROE) |
| `commission` | `0.001` | Trading commission rate (0.1%) |
| `ibkr.host` | `127.0.0.1` | IBKR TWS/Gateway host |
| `ibkr.port` | `7497` | IBKR port (7497=paper, 7496=live) |
| `ibkr.client_id` | `1` | IBKR client ID |
| `data_source` | `yfinance` | Data source (yfinance/polygon) |

**Recommended config.yaml example**:

```yaml
# Risk Parameters
risk:
  stop_loss_pct: -10
  take_profit_pct: 30
  trailing_stop_pct: 10
  max_hold_days: 25
  min_hold_days: 3
  use_macd_sell: false

# Screener Parameters
screener:
  rps_threshold: 85
  rps_periods: [20, 60, 120]
  max_buy: 3
  max_own: 5
  use_fundamentals: false

# IBKR Connection
ibkr:
  host: "127.0.0.1"
  port: 7497
  client_id: 1
  timeout: 30

# Data Source
data_source: "yfinance"
polygon_api_key: ""
commission: 0.001
```

**.env example**:

```bash
# Polygon.io API Key (optional, for premium data)
POLYGON_API_KEY="your_polygon_api_key"

# IBKR Configuration (optional, can also be set in config.yaml)
IBKR_HOST="127.0.0.1"
IBKR_PORT="7497"
IBKR_CLIENT_ID="1"
```

### How to Get API Keys:

**Polygon.io** (optional, for real-time/premium data):
1. Visit https://polygon.io/
2. Sign up for an account (free tier available)
3. Navigate to Dashboard → API Keys
4. Copy your API key

**Interactive Brokers** (for trading):
1. Open a paper trading account
2. Download and install TWS or IB Gateway
3. Enable API settings: File → Global Configuration → API → Settings
4. Enable "Enable ActiveX and Socket Clients", set port to 7497 (paper)

## Environment Check

Before first use, install dependencies:

```bash
pip install -r {baseDir}/requirements.txt
```

Check items: Python version | Dependencies | Database connectivity | IBKR connection (optional) | API keys (optional)

**If any check fails**, provide fix guidance:

| Check Item | Fix Method |
|------------|-------------|
| Python version | Install Python 3.10+: `conda create -n openclaw python=3.10` |
| Dependencies | Run `pip install -r {baseDir}/requirements.txt` |
| Database | Ensure `data/` directory is writable |
| IBKR connection | Start TWS/IB Gateway, enable API, set port 7497 |
| Polygon API key | Configure in .env or config.yaml |

## Workflow Overview

Copy this checklist and check items as you progress:

```
Talon-Trade Execution Progress:
- [ ] Step 0: Load preferences (config.yaml, .env), determine execution parameters
- [ ] Step 1: Download/update historical data (first-time full download, then incremental)
- [ ] Step 2: Run RPS screener to identify candidate stocks
- [ ] Step 3: Execute trades (buy candidates, sell based on exit rules)
- [ ] Step 4: Monitor positions (stop-loss/take-profit checks)
- [ ] Step 5: Run backtest (optional, for strategy validation)
- [ ] Step 6: Report complete
```

### Step 0: Load Preferences

Check and load config.yaml settings (see Configuration Preferences section above), parse and store default values for subsequent steps.

### Step 1: Download/Update Data

**First-time full download** (2 years of S&P 500 historical data):

```bash
cd {baseDir}/scripts
python main.py --step update
```

**Daily incremental update** (automatically skips already downloaded data):

```bash
python main.py --step update
```

**Force refresh** (redownload all data):

```bash
python main.py --step update --force-refresh
```

**Data Storage**:
- Database: `{baseDir}/data/db/market_data.db`
- Logs: `{baseDir}/data/logs/`
- Cache: `{baseDir}/data/cache/`
- Backtest results: `{baseDir}/data/backtest/`

### Step 2: Run RPS Screener

Generate candidate stock list based on RPS and multi-factor scoring:

```bash
cd {baseDir}/scripts
python main.py --step screen
```

**Output**: `{baseDir}/data/cache/rps_candidates.json`

**Screening Logic**:
1. Calculate RPS for 20/60/120-day periods
2. Filter stocks with all periods RPS ≥ threshold (default 85)
3. Calculate composite score (RPS 50% + Volume 20% + Fundamentals 30%)
4. Sort by score and output top candidates

### Step 3: Execute Trades

**Paper trading (dry-run mode)** - no actual orders:

```bash
cd {baseDir}/scripts
python main.py --step trade --dry-run
```

**Paper trading (live paper account)**:

```bash
python main.py --step trade
```

**Position Management Logic**:
- Target position size = Net Asset Value / `max_own`
- Maximum `max_buy` new stocks per day
- Only buy stocks not already in portfolio
- If cash insufficient, allocate proportionally

**Exit Rules** (checked daily):

| Rule | Condition |
|------|-----------|
| Stop Loss | P&L ≤ `stop_loss_pct` |
| Trailing Stop | Drawdown from peak ≥ `trailing_stop_pct` |
| MACD Death Cross | MACD line crosses below signal line |
| Take Profit | P&L ≥ `take_profit_pct` |
| Time Stop | Held for `max_hold_days` days without profit |

### Step 4: Monitor Positions

Run stop-loss/take-profit monitoring (can be scheduled during trading hours):

```bash
cd {baseDir}/scripts
python main.py --step monitor
```

**With custom duration and interval**:

```bash
python main.py --step monitor --monitor-duration 390 --monitor-interval 30
```

### Step 5: Run Backtest

Validate strategy performance with historical data:

```bash
cd {baseDir}/scripts
python main.py --step backtest
```

**Backtest Output**:
- Total return, annualized return, Sharpe ratio
- Win rate, average profit/loss
- Maximum drawdown
- Monthly returns table
- Equity curve chart
- Drawdown curve chart

### Step 6: Complete Workflow

Run full workflow (update → screen → trade → monitor):

```bash
cd {baseDir}/scripts
python main.py --step all
```

**With dry-run** (no actual orders):

```bash
python main.py --step all --dry-run
```

## Detailed Feature Description

### Data Management Module

| Function | Purpose | Cache | Incremental |
|----------|---------|-------|-------------|
| `download_full_history()` | Download 2 years of historical data | SQLite | ✓ |
| `daily_update()` | Download latest trading data | SQLite | ✓ |
| `get_data()` | Read data from local database | SQLite | - |

**Data Fields**:
- OHLCV (Open, High, Low, Close, Volume)
- Adjusted close (for split/dividend adjustment)
- Dividends and split ratios

### RPS Calculation Module

| Period | Description |
|--------|-------------|
| 20-day | Short-term momentum |
| 60-day | Medium-term trend |
| 120-day | Long-term trend |
| 250-day | Yearly trend (optional) |

**RPS Formula**:
```
RPS = (Rank of stock's return / Total stocks) × 100
```

### Multi-Factor Scoring

| Factor | Weight | Description |
|--------|--------|-------------|
| RPS Average | 50% | Average of all RPS periods |
| Volume Factor | 20% | Current volume / 20-day average volume |
| Fundamentals | 30% | PE ratio + ROE (optional, can be disabled) |

### IBKR Integration

| Feature | Paper Trading | Live Trading |
|---------|---------------|--------------|
| Port | 7497 | 7496 |
| Order Types | MARKET, LIMIT, STOP | MARKET, LIMIT, STOP |
| Fractional Shares | Supported | Supported (if enabled) |
| Market Data | Delayed (15 min) | Real-time (with subscription) |

## Feature Comparison

| Feature | Data Management | RPS Screener | Backtest | Paper Trading | Live Trading |
|---------|-----------------|--------------|----------|---------------|--------------|
| S&P 500 data | ✓ | - | ✓ | - | - |
| Incremental updates | ✓ | - | - | - | - |
| RPS calculation | - | ✓ | ✓ | - | - |
| Multi-factor scoring | - | ✓ | ✓ | - | - |
| Dynamic exit rules | - | - | ✓ | ✓ | ✓ |
| Position management | - | - | ✓ | ✓ | ✓ |
| Stop-loss monitoring | - | - | ✓ | ✓ | ✓ |
| Dry-run mode | - | - | - | ✓ | - |
| Real orders | - | - | - | ✓ | ✓ |
| Performance charts | - | - | ✓ | - | - |

## Prerequisites

**Required**:
- Python 3.10+
- Dependencies: `pip install -r requirements.txt`
- Internet connection for data download

**Optional**:
- Interactive Brokers account (paper or live)
- Polygon.io API key (for premium data)
- TWS or IB Gateway installed

**Configuration Locations** (priority order):
1. CLI parameters
2. config.yaml
3. Environment variables
4. Default values

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Cannot connect to IBKR | Start TWS/IB Gateway, enable API, set port 7497, add trusted IP |
| No market data | Run `--step update` to download data first |
| Rate limited by data source | Increase `request_delay`, use Polygon.io premium |
| Backtest shows no trades | Lower `rps_threshold`, check data completeness |
| Orders rejected | Check account permissions, fractional share settings |
| Price is NaN | Use local database price (automatically falls back) |
| Database locked | Close other connections, restart script |
| Timeout error | Increase `timeout` in config.yaml |

## Extension Support

Customize via config.yaml. See the **Configuration Preferences** section for supported options.

**Adding New Factors**:
1. Edit `{baseDir}/scripts/core/factors.py`
2. Add new factor calculation function
3. Integrate into `score_stock()` with desired weight

**Adding New Exit Rules**:
1. Edit `{baseDir}/scripts/analysis/backtest.py` and `{baseDir}/scripts/trading/stop_loss_monitor.py`
2. Add new condition in sell check section
3. Add corresponding parameter in config.yaml

## Related References

| Topic | Reference |
|-------|-----------|
| AkShare Documentation | https://akshare.akfamily.xyz/ |
| Interactive Brokers API | https://www.interactivebrokers.com/api/doc.html |
| ib_insync Library | https://ib-insync.readthedocs.io/ |
| Polygon.io API | https://polygon.io/docs |
| yfinance Library | https://github.com/ranaroussi/yfinance |

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-04-02 | Initial release with modular structure |
