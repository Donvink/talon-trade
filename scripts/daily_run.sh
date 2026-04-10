#!/bin/bash
# scripts/daily_run.sh

cd /mnt/d/projects/quant-trade/skills/quant-trade/scripts
source /home/zhong/miniconda3/etc/profile.d/conda.sh
conda activate openclaw

# 运行完整流程
python main.py --step all

echo "每日运行完成: $(date)" >> ../../logs/daily_run.log