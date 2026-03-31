---
name: talon-trade
description: |
  美股趋势选股与自动交易技能。基于RPS（相对强度）和多因子评分，筛选强势股，并支持通过Interactive Brokers执行交易。
  功能包括：历史数据下载、每日增量更新、RPS计算、多因子评分、回测、模拟盘交易、止损止盈监控。
metadata:
  openclaw:
    data_dir: ~/.openclaw/data/talon_trade
    requires:
      bins: ["python3"]
      env: ["POLYGON_API_KEY"]
      config: ["trading.enabled"]
---

# Talon Trade Skill

## 数据存储
所有持久化数据（数据库、日志）存储在 `~/.openclaw/data/talon_trade/` 目录下。

## 使用方式
- 在OpenClaw对话中触发：
  - “运行RPS选股” → 执行 `scripts/screener.py`
  - “回测RPS策略” → 执行 `scripts/backtest.py`
  - “自动买入候选” → 读取候选列表并调用IBKR下单
- 手动运行脚本：
  ```bash
  cd ~/.openclaw/workspace/skills/talon-trade
  python scripts/screener.py