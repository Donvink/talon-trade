# talon-trade
TalonTrade is a modular AI-powered system for US stock analysis and automated trading. It integrates technical analysis, fundamental screening, news sentiment analysis, risk control, and Interactive Brokers execution—designed as a collection of skills for OpenClaw agents, with a roadmap to become a standalone cross-platform trading assistant.


https://www.interactivebrokers.com/

下载：去 盈透证券官网 搜索下载TWS (Trader Workstation)。
安装：像安装普通软件一样完成安装。
启动：打开软件，在登录界面的登录方式/账户类型里，一定要选择 Paper Trading（模拟交易/纸交）。用你的模拟账户用户名和密码登录


~/.openclaw/workspace/skills/talon-trade/
├── SKILL.md
├── scripts/
│   ├── __init__.py
│   ├── config.py
│   ├── data_manager.py
│   ├── stock_pool.py
│   ├── rps_calculator.py
│   ├── factors.py
│   ├── screener.py
│   ├── backtest.py
│   ├── ibkr_client.py
│   ├── risk_checker.py
│   └── stop_loss_monitor.py
├── references/
│   └── rps_method.md
└── hooks/
    └── pre_execution.sh


使用说明
安装依赖：

bash
pip install pandas numpy requests yfinance ib_insync
首次全量下载历史数据：

bash
cd ~/.openclaw/workspace/skills/talon-trade
python -c "from scripts.data_manager import DataManager; from scripts.stock_pool import get_sp500_symbols; dm = DataManager(); dm.download_full_history(get_sp500_symbols()); dm.close()"
每日更新（可设置cron）：

bash
python -c "from scripts.data_manager import DataManager; from scripts.stock_pool import get_sp500_symbols; dm = DataManager(); dm.daily_update(get_sp500_symbols()); dm.close()"
运行RPS选股：

bash
python scripts/screener.py
运行回测：

bash
python scripts/backtest.py
启动IBKR模拟盘（端口7497），然后测试下单：

bash
python scripts/ibkr_client.py --order --symbol AAPL --side BUY --quantity 1









~/.openclaw/workspace/skills/
├── us-stock-data/
│   └── SKILL.md
├── technical-analysis/
│   ├── SKILL.md
│   └── scripts/
│       └── indicators.py
├── fundamental-analysis/
│   └── SKILL.md
├── news-analysis/
│   ├── SKILL.md
│   └── scripts/
│       └── sentiment.py
├── ibkr-executor/
│   ├── SKILL.md
│   ├── scripts/
│   │   └── ibkr_client.py
│   └── references/
│       └── api_docs.md
└── risk-control/
    ├── SKILL.md
    └── scripts/
        └── risk_checker.py






                ┌────────────────────┐
                │      Agent         │
                └────────┬───────────┘
                         │
    ┌──────────────┬──────────────┬──────────────┐
    ↓              ↓              ↓              ↓
Technical   Fundamental     News Analysis   Risk Control
Analysis    Analysis
    ↓              ↓              ↓              ↓
                ───── 汇总评分 ─────
                         ↓
                Portfolio Agent（最终决策）
                         ↓
                    Place Order



## 🧩 1️⃣ Skills（最关键）

### 📈 技术分析 Skill

```python
def technical_analysis(symbol):
    price = get_price(symbol)
    
    ma20 = calc_ma(price, 20)
    ma50 = calc_ma(price, 50)

    trend = "bullish" if ma20 > ma50 else "bearish"

    return {
        "trend": trend,
        "confidence": 0.7
    }
```

---

### 📊 基本面 Skill

```python
def fundamental_analysis(symbol):
    data = get_fundamentals(symbol)

    score = compute_growth_score(data)

    return {
        "score": score,
        "quality": "high" if score > 0.7 else "medium"
    }
```

---

### 🧠 新闻分析 Skill

```python
def news_analysis(symbol):
    news = get_news(symbol)

    summary = llm_call(f"""
    Analyze sentiment and AI relevance:
    {news}
    """)

    return summary
```

---

### ⚠️ 风控 Skill

```python
def risk_control(symbol):
    vol = get_volatility(symbol)

    return {
        "risk": "high" if vol > 0.4 else "medium",
        "position_limit": 0.1
    }
```

---

### 💰 下单 Skill（实盘接口）

接 Interactive Brokers：

```python
def place_order(symbol, action, size):
    ib.placeOrder(...)
```

---

## 🤖 2️⃣ Agent（用 Skill 组合）


### 🟢 Market Agent

```python
market_agent = Agent(
    name="market_agent",
    skills=[technical_analysis],
    instruction="Analyze market trend and return structured result"
)
```

---

### 🔵 Fundamental Agent

```python
fund_agent = Agent(
    name="fund_agent",
    skills=[fundamental_analysis],
)
```

---

### 🟣 News Agent

```python
news_agent = Agent(
    name="news_agent",
    skills=[news_analysis],
)
```

---

### 🔴 Portfolio Agent（核心）

```python
portfolio_agent = Agent(
    name="portfolio_agent",
    skills=[technical_analysis, fundamental_analysis, news_analysis, risk_control],
    instruction="""
    Combine all signals and decide:
    BUY / SELL / HOLD
    Return JSON
    """
)
```

---

# 🔄 三、Workflow


## 单股票流程：

```python
workflow = [
    ("market_agent", "analyze trend of NVDA"),
    ("fund_agent", "analyze fundamentals of NVDA"),
    ("news_agent", "analyze news of NVDA"),
    ("portfolio_agent", "make final decision")
]
```

---

## 批量扫描：

```python
for symbol in sp500_list:
    run_workflow(symbol)
```

---


> **Daily Stock Selection Pipeline（每天自动跑）**

---

# 🚀 四、真正的“OpenClaw优势玩法”（关键区别）

## 🔥 1. 真正执行（Execution Agent）

不仅推荐，还能：

* 自动下单
* 自动调仓
* 自动止损


## 🔥 2. 自反馈系统（非常加分）

```python
def reflect():
    trades = load_trade_history()

    return llm_call(f"""
    Analyze mistakes:
    {trades}
    Suggest improvements
    """)
```

👉 Agent 会：

* 发现自己判断错
* 自动优化策略

---

## 🔥 3. 事件驱动（高级）

不是每天跑，而是：

```text
IF:
- earnings released
- stock > MA50
- news sentiment spike

THEN:
→ trigger agent
```





