---
name: talon-trade
description: 基于 RPS（相对强度）多因子选股的美股量化交易系统，支持回测、模拟盘和实盘交易，对接 Interactive Brokers
version: 1.0.0
metadata:
  openclaw:
    homepage: https://github.com/yourname/talon-trade
    requires:
      anyBins:
        - python3
        - python
---

# 🦞 Talon-Trade 美股量化交易系统

👉 **[GitHub 仓库](https://github.com/yourname/talon-trade)**

## 语言

**匹配用户语言**：使用与用户相同的语言回复。如果用户使用中文，则用中文回复；如果用户使用英文，则用英文回复。

## 脚本目录

**Agent 执行**：本 SKILL.md 所在目录为 `{baseDir}`，使用 `{baseDir}/scripts/<name>.py` 执行脚本。确保 Python 3.10+ 已安装并配置依赖。

| 脚本 | 用途 |
|------|------|
| `scripts/main.py` | 主执行脚本，协调整个工作流程 |
| `scripts/backtest.py` | RPS 策略回测，支持动态退出规则 |
| `scripts/screener.py` | RPS 选股和多因子评分 |
| `scripts/data_manager.py` | 本地数据管理（SQLite、下载、增量更新） |
| `scripts/ibkr_client.py` | Interactive Brokers API 客户端（模拟盘/实盘） |
| `scripts/risk_checker.py` | 风控检查和订单验证 |
| `scripts/stop_loss_monitor.py` | 止损/止盈监控 |
| `scripts/rps_calculator.py` | RPS（相对强度）计算 |
| `scripts/factors.py` | 多因子评分（成交量、基本面等） |
| `scripts/stock_pool.py` | 标普500成分股管理 |
| `scripts/generate_report.py` | 生成回测报告（资产曲线、月度收益） |

## 配置说明

1. 检查 config.yaml 是否存在：`{baseDir}/talon-trade/config.yaml`

2. 检查 .env 文件是否配置了 API 密钥：`{baseDir}/talon-trade/.env`

**config.yaml 支持**：风险参数 | 选股参数 | IBKR 连接设置 | 数据源选择 | 交易佣金
**.env 支持**：数据源 API 密钥（Polygon.io 等）

**最小支持配置项**：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `rps_threshold` | `85` | RPS 选股阈值（0-100） |
| `rps_periods` | `[20, 60, 120]` | RPS 计算周期（天） |
| `max_buy` | `3` | 每日最多买入股票数量 |
| `max_own` | `5` | 最多持有股票数量 |
| `stop_loss_pct` | `-10` | 固定止损百分比 |
| `take_profit_pct` | `30` | 止盈百分比 |
| `trailing_stop_pct` | `10` | 移动止损回撤百分比 |
| `max_hold_days` | `25` | 最大持有天数（时间止损） |
| `min_hold_days` | `3` | 最小持有天数 |
| `use_macd_sell` | `false` | 是否使用 MACD 死叉卖出 |
| `use_fundamentals` | `false` | 是否使用基本面因子（PE/ROE） |
| `commission` | `0.001` | 交易佣金率（0.1%） |
| `ibkr.host` | `127.0.0.1` | IBKR TWS/Gateway 主机地址 |
| `ibkr.port` | `7497` | IBKR 端口（7497=模拟盘，7496=实盘） |
| `ibkr.client_id` | `1` | IBKR 客户端 ID |
| `data_source` | `yfinance` | 数据源（yfinance/polygon） |

**推荐 config.yaml 示例**：

```yaml
# 风险参数
risk:
  stop_loss_pct: -10
  take_profit_pct: 30
  trailing_stop_pct: 10
  max_hold_days: 25
  min_hold_days: 3
  use_macd_sell: false

# 选股参数
screener:
  rps_threshold: 85
  rps_periods: [20, 60, 120]
  max_buy: 3
  max_own: 5
  use_fundamentals: false

# IBKR 连接配置
ibkr:
  host: "127.0.0.1"
  port: 7497
  client_id: 1
  timeout: 30

# 数据源
data_source: "yfinance"
polygon_api_key: ""
commission: 0.001
```

**.env 示例**：

```bash
# Polygon.io API Key（可选，用于付费数据）
POLYGON_API_KEY="your_polygon_api_key"

# IBKR 配置（可选，也可在 config.yaml 中设置）
IBKR_HOST="127.0.0.1"
IBKR_PORT="7497"
IBKR_CLIENT_ID="1"
```

### 如何获取 API 密钥：

**Polygon.io**（可选，用于实时/付费数据）：
1. 访问 https://polygon.io/
2. 注册账户（免费套餐可用）
3. 进入 Dashboard → API Keys
4. 复制 API 密钥

**Interactive Brokers**（用于交易）：
1. 开立模拟交易账户
2. 下载安装 TWS 或 IB Gateway
3. 启用 API 设置：File → Global Configuration → API → Settings
4. 勾选 "Enable ActiveX and Socket Clients"，端口设置为 7497（模拟盘）

## 环境检查

首次使用前，安装依赖：

```bash
pip install -r {baseDir}/requirements.txt
```

检查项目：Python 版本 | 依赖包 | 数据库连接 | IBKR 连接（可选）| API 密钥（可选）

**检查失败时的修复方法**：

| 检查项 | 修复方法 |
|--------|----------|
| Python 版本 | 安装 Python 3.10+：`conda create -n openclaw python=3.10` |
| 依赖包 | 运行 `pip install -r {baseDir}/requirements.txt` |
| 数据库 | 确保 `data/` 目录可写 |
| IBKR 连接 | 启动 TWS/IB Gateway，启用 API，端口设置为 7497 |
| Polygon API 密钥 | 在 .env 或 config.yaml 中配置 |

## 工作流程概览

复制此清单，逐项勾选进度：

```
Talon-Trade 执行进度：
- [ ] 步骤 0：加载配置（config.yaml, .env），确定执行参数
- [ ] 步骤 1：下载/更新历史数据（首次全量，后续增量）
- [ ] 步骤 2：运行 RPS 选股，识别候选股票
- [ ] 步骤 3：执行交易（买入候选，根据退出规则卖出）
- [ ] 步骤 4：监控持仓（止损/止盈检查）
- [ ] 步骤 5：运行回测（可选，用于策略验证）
- [ ] 步骤 6：报告完成
```

### 步骤 0：加载配置

检查并加载 config.yaml 设置（参见上方配置说明），解析并存储默认值供后续步骤使用。

### 步骤 1：下载/更新数据

**首次全量下载**（2年标普500历史数据）：

```bash
python {baseDir}/scripts/main.py --step update
```

**每日增量更新**（自动跳过已下载数据）：

```bash
python {baseDir}/scripts/main.py --step update
```

**强制刷新**（重新下载所有数据）：

```bash
python {baseDir}/scripts/main.py --step update --force-refresh
```

**数据存储位置**：
- 数据库：`~/.openclaw/data/talon_trade/market_data.db`
- 日志：`~/.openclaw/data/talon_trade/logs/`
- 缓存：`~/.openclaw/data/talon_trade/`

### 步骤 2：运行 RPS 选股

基于 RPS 和多因子评分生成候选股票列表：

```bash
python {baseDir}/scripts/main.py --step screen
```

**输出文件**：`~/.openclaw/data/talon_trade/rps_candidates.json`

**选股逻辑**：
1. 计算 20/60/120 日 RPS
2. 筛选所有周期 RPS ≥ 阈值（默认85）的股票
3. 计算综合评分（RPS 50% + 成交量 20% + 基本面 30%）
4. 按评分排序输出候选股票

### 步骤 3：执行交易

**模拟盘（dry-run 模式）** - 不实际下单：

```bash
python {baseDir}/scripts/main.py --step trade --dry-run
```

**模拟盘（真实模拟账户）**：

```bash
python {baseDir}/scripts/main.py --step trade
```

**仓位管理逻辑**：
- 目标仓位 = 净资产 / `max_own`
- 每日最多买入 `max_buy` 只新股票
- 只买入未持仓的股票
- 现金不足时按比例分配

**退出规则**（每日检查）：

| 规则 | 触发条件 |
|------|----------|
| 固定止损 | 盈亏 ≤ `stop_loss_pct` |
| 移动止损 | 从最高点回撤 ≥ `trailing_stop_pct` |
| MACD 死叉 | MACD 线下穿信号线 |
| 止盈 | 盈亏 ≥ `take_profit_pct` |
| 时间止损 | 持有 `max_hold_days` 天仍未止盈 |

### 步骤 4：监控持仓

运行止损/止盈监控（可在交易时段内定时执行）：

```bash
python {baseDir}/scripts/main.py --step monitor
```

**自定义监控时长和间隔**：

```bash
python {baseDir}/scripts/main.py --step monitor --monitor-duration 390 --monitor-interval 30
```

### 步骤 5：运行回测

使用历史数据验证策略表现：

```bash
python {baseDir}/scripts/main.py --step backtest
```

**回测输出内容**：
- 总收益率、年化收益率、夏普比率
- 胜率、平均盈利/亏损
- 最大回撤
- 月度收益表
- 资产曲线图
- 回撤曲线图

### 步骤 6：完整工作流程

运行完整流程（更新数据 → 选股 → 交易 → 监控）：

```bash
python {baseDir}/scripts/main.py --step all
```

**模拟模式**（不实际下单）：

```bash
python {baseDir}/scripts/main.py --step all --dry-run
```

## 功能详解

### 数据管理模块

| 函数 | 用途 | 缓存 | 增量 |
|------|------|------|------|
| `download_full_history()` | 下载2年历史数据 | SQLite | ✓ |
| `daily_update()` | 下载最新交易日数据 | SQLite | ✓ |
| `get_data()` | 从本地数据库读取数据 | SQLite | - |

**数据字段**：
- OHLCV（开、高、低、收、量）
- 复权收盘价（用于分红/拆股调整）
- 股息和拆股比例

### RPS 计算模块

| 周期 | 说明 |
|------|------|
| 20日 | 短期动量 |
| 60日 | 中期趋势 |
| 120日 | 长期趋势 |
| 250日 | 年度趋势（可选） |

**RPS 计算公式**：
```
RPS = (股票涨幅排名 / 总股票数) × 100
```

### 多因子评分

| 因子 | 权重 | 说明 |
|------|------|------|
| RPS 平均分 | 50% | 所有 RPS 周期的平均值 |
| 成交量因子 | 20% | 当前成交量 / 20日均量 |
| 基本面因子 | 30% | 市盈率 + ROE（可选，可关闭） |

### IBKR 集成

| 功能 | 模拟盘 | 实盘 |
|------|--------|------|
| 端口 | 7497 | 7496 |
| 订单类型 | MARKET, LIMIT, STOP | MARKET, LIMIT, STOP |
| 碎股交易 | 支持 | 支持（需开通权限） |
| 行情数据 | 延迟15分钟 | 实时（需订阅） |

## 功能对比

| 功能 | 数据管理 | RPS选股 | 回测 | 模拟盘 | 实盘 |
|------|----------|---------|------|--------|------|
| 标普500数据 | ✓ | - | ✓ | - | - |
| 增量更新 | ✓ | - | - | - | - |
| RPS计算 | - | ✓ | ✓ | - | - |
| 多因子评分 | - | ✓ | ✓ | - | - |
| 动态退出规则 | - | - | ✓ | ✓ | ✓ |
| 仓位管理 | - | - | ✓ | ✓ | ✓ |
| 止损监控 | - | - | ✓ | ✓ | ✓ |
| 模拟模式 | - | - | - | ✓ | - |
| 真实下单 | - | - | - | ✓ | ✓ |
| 绩效图表 | - | - | ✓ | - | - |

## 前置要求

**必需**：
- Python 3.10+
- 依赖包：`pip install -r requirements.txt`
- 网络连接（用于下载数据）

**可选**：
- Interactive Brokers 账户（模拟盘或实盘）
- Polygon.io API 密钥（用于付费数据）
- TWS 或 IB Gateway 客户端

**配置优先级**（从高到低）：
1. 命令行参数
2. config.yaml
3. 环境变量
4. 默认值

## 故障排除

| 问题 | 解决方案 |
|------|----------|
| 无法连接 IBKR | 启动 TWS/IB Gateway，启用 API，端口 7497，添加受信任 IP |
| 无行情数据 | 先运行 `--step update` 下载数据 |
| 数据源限流 | 增加 `request_delay`，使用 Polygon.io 付费版 |
| 回测无交易 | 降低 `rps_threshold`，检查数据完整性 |
| 订单被拒绝 | 检查账户权限、碎股交易设置 |
| 价格显示 NaN | 自动使用本地数据库价格（已内置降级） |
| 数据库锁定 | 关闭其他连接，重启脚本 |
| 连接超时 | 增加 config.yaml 中的 `timeout` 值 |

## 扩展支持

通过 config.yaml 进行自定义配置。支持的配置项请参见上方**配置说明**。

**添加新因子**：
1. 编辑 `scripts/factors.py`
2. 添加新因子计算函数
3. 在 `score_stock()` 中集成并设置权重

**添加新退出规则**：
1. 编辑 `scripts/backtest.py` 和 `scripts/stop_loss_monitor.py`
2. 在卖出检查部分添加新条件
3. 在 config.yaml 中添加对应参数

## 相关参考

| 主题 | 参考链接 |
|------|----------|
| AkShare 文档 | https://akshare.akfamily.xyz/ |
| Interactive Brokers API | https://www.interactivebrokers.com/api/doc.html |
| ib_insync 库 | https://ib-insync.readthedocs.io/ |
| Polygon.io API | https://polygon.io/docs |
| yfinance 库 | https://github.com/ranaroussi/yfinance |

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| 1.0.0 | 2026-04-02 | 初始版本 |
