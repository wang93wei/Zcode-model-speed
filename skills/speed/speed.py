#!/usr/bin/env python3
"""ZCode 模型输出速度统计。

解析 ~/.zcode/cli/rollout/model-io-*.jsonl（ZCode 对每次模型请求的本地记录），
计算输出速度（tokens/sec）、耗时与 token 用量。

用法:
  python speed.py               当前(最新)会话: 最近 10 条请求 + 会话汇总
  python speed.py --last 30     最近 30 条请求
  python speed.py --all         所有会话按模型汇总
  python speed.py --session <session-id 前缀>   指定会话

口径说明: 速度 = response.usage.outputTokens / durationMs * 1000。
durationMs 是一次流式响应的总时长（含思考与工具调用参数生成），
outputTokens 为该次响应的总输出 token（含思考 token），与 API 计费口径一致。
"""

import argparse
import glob
import json
import os
import statistics
import sys
from datetime import datetime

ROLLOUT_GLOB = os.path.join(
    os.path.expanduser("~"), ".zcode", "cli", "rollout", "model-io-*.jsonl"
)


def load_records(paths):
    """逐行读取 rollout 文件，返回可计算速度的记录列表。"""
    records = []
    skipped = 0
    for path in paths:
        session_id = os.path.basename(path)[len("model-io-"):-len(".jsonl")]
        is_subagent = "subagent" in session_id
        try:
            with open(path, encoding="utf-8") as fp:
                for line in fp:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        skipped += 1
                        continue
                    usage = (d.get("response") or {}).get("usage") or {}
                    out_tok = usage.get("outputTokens") or 0
                    dur = d.get("durationMs") or 0
                    if out_tok <= 0 or dur <= 0:
                        skipped += 1
                        continue
                    records.append({
                        "session": session_id,
                        "subagent": is_subagent,
                        "model": (d.get("model") or {}).get("modelId") or "unknown",
                        "started": d.get("startedAt") or "",
                        "dur_ms": dur,
                        "out_tok": out_tok,
                        "in_tok": usage.get("inputTokens") or 0,
                        "cache_read": usage.get("cacheReadTokens") or 0,
                        "tps": out_tok / (dur / 1000.0),
                    })
        except OSError:
            skipped += 1
    records.sort(key=lambda r: r["started"])
    return records, skipped


def fmt_time(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%m-%d %H:%M")
    except (ValueError, AttributeError):
        return (iso or "")[:16]


def stats_line(recs, label):
    tps = [r["tps"] for r in recs]
    total_out = sum(r["out_tok"] for r in recs)
    total_dur = sum(r["dur_ms"] for r in recs)
    overall = total_out / (total_dur / 1000.0) if total_dur else 0.0
    s = sorted(tps)
    p95 = s[min(len(s) - 1, int(len(s) * 0.95))]
    return (
        f"{label}: {len(recs)} 次请求 | "
        f"总耗时 {total_dur/1000:.1f}s | 总输出 {total_out:,} tok | "
        f"输入 {sum(r['in_tok'] for r in recs):,} tok "
        f"(缓存命中 {sum(r['cache_read'] for r in recs):,})\n"
        f"  输出速度 tok/s: 加权平均 {overall:.1f} | 中位 {statistics.median(tps):.1f} | "
        f"P95 {p95:.1f} | 最快 {max(tps):.1f} | 最慢 {min(tps):.1f}"
    )


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(description="ZCode 模型输出速度统计")
    ap.add_argument("--last", type=int, default=10, metavar="N", help="显示最近 N 条请求 (默认 10)")
    ap.add_argument("--all", action="store_true", help="所有会话按模型汇总")
    ap.add_argument("--session", metavar="ID", help="指定会话 ID 前缀")
    args = ap.parse_args()

    paths = sorted(glob.glob(ROLLOUT_GLOB), key=os.path.getmtime)
    if not paths:
        print("未找到 rollout 记录: %s" % ROLLOUT_GLOB)
        return 1

    if args.session:
        paths = [p for p in paths if args.session in os.path.basename(p)]
        if not paths:
            print("没有匹配会话前缀 %r 的记录" % args.session)
            return 1
        latest = paths
    else:
        latest = [paths[-1]]

    records, skipped = load_records(paths if (args.all or args.session) else latest)
    if not records:
        print("没有可统计的请求记录（找到 %d 条被跳过: 无输出 token 或时长为 0）" % skipped)
        return 1

    if args.all:
        print("== 全部会话 (按模型汇总) ==\n")
        models = {}
        for r in records:
            models.setdefault(r["model"], []).append(r)
        for model in sorted(models):
            print(stats_line(models[model], model))
            sub = [r for r in models[model] if r["subagent"]]
            if sub:
                print("  其中子代理请求 %d 次" % len(sub))
        print("\n会话数: %d | 跳过无效记录: %d" % (len(paths), skipped))
        return 0

    sid = latest[0] and os.path.basename(latest[0])
    print("== 会话 %s ==\n" % sid)
    print(stats_line(records, "汇总"))
    if skipped:
        print("  (跳过无效记录: %d)" % skipped)

    main_recs = [r for r in records if not r["subagent"]]
    shown = main_recs[-args.last:]
    sub_count = len(records) - len(main_recs)
    if sub_count:
        print("  (另有子代理请求 %d 次，未列入明细)" % sub_count)

    print("\n最近 %d 条请求:" % len(shown))
    print("时间       | 模型    | 耗时(s) | 输出tok | tok/s")
    print("-" * 58)
    for r in shown:
        print("%s | %-7s | %6.1f  | %7d | %5.1f" % (
            fmt_time(r["started"]), r["model"][:7], r["dur_ms"] / 1000.0,
            r["out_tok"], r["tps"]))
    print("\n(速度 = 输出token数/流式响应总时长, 含思考与工具参数生成)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
