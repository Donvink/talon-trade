#!/bin/bash
# 可选：在执行交易前运行的风控钩子
echo "Pre-execution hook: checking market hours..."
# 简单检查当前时间是否在美股交易时段（示例）
HOUR=$(date +%H)
if [ $HOUR -lt 9 ] || [ $HOUR -gt 16 ]; then
    echo "Outside market hours, trading disabled."
    exit 1
fi
exit 0