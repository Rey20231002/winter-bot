#!/usr/bin/env python3
"""
API 费用跟踪工具

跟踪 DeepSeek API 的使用情况和预估费用。

用法:
    python cost_tracker.py --log-dir ../AstrBot/data/ --days 7
"""

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# DeepSeek V3 定价 (2025)
# 输入: $0.27 / 百万 tokens (缓存命中: $0.07)
# 输出: $1.10 / 百万 tokens
PRICING = {
    "deepseek-chat": {
        "input_per_1m": 0.27,
        "output_per_1m": 1.10,
        "cache_hit_per_1m": 0.07,
    },
    "deepseek-reasoner": {
        "input_per_1m": 0.55,
        "output_per_1m": 2.19,
        "cache_hit_per_1m": 0.14,
    },
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> dict:
    """估算单次调用费用"""
    pricing = PRICING.get(model, PRICING["deepseek-chat"])

    input_cost = (prompt_tokens / 1_000_000) * pricing["input_per_1m"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output_per_1m"]
    total_cost = input_cost + output_cost

    return {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "total_cost": round(total_cost, 6),
        "total_cost_cny": round(total_cost * 7.2, 4),  # USD to CNY
    }


def main():
    parser = argparse.ArgumentParser(description="LLM API 费用跟踪工具")
    parser.add_argument("--log-dir", type=str, help="AstrBot 日志目录")
    parser.add_argument("--days", type=int, default=7, help="统计天数 (默认: 7)")

    args = parser.parse_args()

    print("=" * 60)
    print("💰 DeepSeek API 费用预估")
    print("=" * 60)
    print()
    print("定价参考 (每百万 tokens):")
    print(f"  deepseek-chat:    输入 $0.27 | 输出 $1.10 | 缓存命中 $0.07")
    print(f"  deepseek-reasoner: 输入 $0.55 | 输出 $2.19 | 缓存命中 $0.14")
    print()

    # 示例：预估典型对话场景的费用
    print("📊 典型场景费用预估:")
    print()

    scenarios = [
        ("短对话 (5轮, 约1K tokens)", 800, 400),
        ("中等对话 (15轮, 约3K tokens)", 2500, 1000),
        ("长对话 (50轮, 约10K tokens)", 8000, 3000),
        ("一天活跃使用 (约100轮)", 20000, 8000),
        ("一个月活跃使用 (约3000轮)", 600000, 240000),
    ]

    for name, prompt_tokens, completion_tokens in scenarios:
        result = estimate_cost("deepseek-chat", prompt_tokens, completion_tokens)
        print(f"  {name}:")
        print(f"    ≈ ${result['total_cost']:.4f} (¥{result['total_cost_cny']:.4f})")

    print()
    print("💡 提示:")
    print("  - 充值 ¥10 (约 $1.40) 大约支持 300+ 轮中等长度对话")
    print("  - 设置 DeepSeek 平台的月度消费限额 (如 ¥30/月) 可控制成本")
    print("  - 在 AstrBot WebUI 中可以查看每段对话的 token 用量")
    print("  - 使用 Claude API 费用约为 DeepSeek 的 20-50 倍")


if __name__ == "__main__":
    main()
