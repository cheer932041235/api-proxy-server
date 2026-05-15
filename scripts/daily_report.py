"""
每日成本报表 — 读取 usage.csv 生成摘要
用法: python scripts/daily_report.py [天数，默认7]
"""

import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta


LOG_FILE = "logs/usage.csv"


def load_data(days=7):
    """加载最近 N 天的日志数据"""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    daily = defaultdict(lambda: {
        "cost": 0, "input": 0, "output": 0, "cached": 0, "requests": 0,
        "models": defaultdict(lambda: {"cost": 0, "requests": 0})
    })

    try:
        with open(LOG_FILE, newline="") as f:
            for row in csv.DictReader(f):
                day = row["timestamp"][:10]
                if day < cutoff:
                    continue
                d = daily[day]
                cost = float(row["cost_usd"])
                d["cost"] += cost
                d["input"] += int(row["input_tokens"])
                d["output"] += int(row["output_tokens"])
                d["cached"] += int(row["cached_tokens"])
                d["requests"] += 1
                d["models"][row["model"]]["cost"] += cost
                d["models"][row["model"]]["requests"] += 1
    except FileNotFoundError:
        print(f"日志文件 {LOG_FILE} 不存在，请先运行 proxy 产生日志。")
        sys.exit(1)

    return daily


def print_report(daily):
    """打印报表"""
    print("=" * 70)
    print("  API 代理 — 每日成本报表")
    print("=" * 70)

    print(f"\n{'日期':<12} {'请求数':>6} {'输入 tokens':>12} {'输出 tokens':>12} "
          f"{'缓存命中率':>10} {'费用 (USD)':>12}")
    print("-" * 70)

    total_cost = 0
    total_requests = 0

    for day in sorted(daily):
        d = daily[day]
        cache_rate = (d["cached"] / d["input"] * 100) if d["input"] > 0 else 0
        icon = "🟢" if cache_rate > 80 else ("🟡" if cache_rate > 50 else "🔴")
        print(f"{day:<12} {d['requests']:>6} {d['input']:>12,} {d['output']:>12,} "
              f"{icon}{cache_rate:>8.1f}% ${d['cost']:>11.4f}")
        total_cost += d["cost"]
        total_requests += d["requests"]

    print("-" * 70)
    print(f"{'合计':<12} {total_requests:>6} {'':>12} {'':>12} {'':>10} ${total_cost:>11.4f}")

    # 按模型分组
    model_totals = defaultdict(lambda: {"cost": 0, "requests": 0})
    for d in daily.values():
        for model, stats in d["models"].items():
            model_totals[model]["cost"] += stats["cost"]
            model_totals[model]["requests"] += stats["requests"]

    if model_totals:
        print(f"\n{'模型':<30} {'请求数':>8} {'费用 (USD)':>12} {'占比':>8}")
        print("-" * 60)
        for model in sorted(model_totals, key=lambda m: model_totals[m]["cost"], reverse=True):
            s = model_totals[model]
            pct = (s["cost"] / total_cost * 100) if total_cost > 0 else 0
            print(f"{model:<30} {s['requests']:>8} ${s['cost']:>11.4f} {pct:>7.1f}%")

    # 月度预估
    avg_daily = total_cost / len(daily) if daily else 0
    print(f"\n📊 日均费用: ${avg_daily:.4f}")
    print(f"📊 月度预估 (22工作日): ${avg_daily * 22:.2f}")
    print(f"📊 月度预估 (30天): ${avg_daily * 30:.2f}")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    data = load_data(days)
    if not data:
        print("指定时间范围内无数据。")
    else:
        print_report(data)
