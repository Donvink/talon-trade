#!/bin/bash
# 每日模拟盘自动运行脚本
# 在美股收盘后运行（北京时间 04:00）

cd /mnt/d/projects/talon-trade/skills/talon-trade/scripts

# 激活 conda 环境
source /home/zhong/miniconda3/etc/profile.d/conda.sh
conda activate openclaw

# 运行完整流程
python main.py --step all

# 记录运行时间
echo "每日运行完成: $(date)" >> ../../../logs/daily_run.log