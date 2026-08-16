#!/usr/bin/env python3
"""Stop hook: 汇总自上次通知以来的模型请求，弹系统通知显示输出速度。

由插件的 Stop hook 在每次模型回复结束时调用。读取 ZCode rollout 记录，
用 requestId 水位做增量判定，把新增请求按 turn 汇总成一条通知。
通知走各平台原生通道: Windows toast / macOS 通知中心 / Linux notify-send。
无论如何都退出 0——通知失败绝不能阻塞会话。
"""

import glob
import json
import os
import subprocess
import sys
import tempfile
import time

ROLLOUT_GLOB = os.path.join(
    os.path.expanduser("~"), ".zcode", "cli", "rollout", "model-io-*.jsonl"
)
STATE_PATH = os.path.join(
    os.path.expanduser("~"), ".zcode", "cli", "model-speed-state.json"
)
PS1_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "toast.ps1")
MAX_SEEN = 500  # 滚动保留的 requestId 水位数量，防状态文件膨胀


def scan_records():
    records = []
    for path in glob.glob(ROLLOUT_GLOB):
        is_sub = "subagent" in os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as fp:
                for line in fp:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    usage = (d.get("response") or {}).get("usage") or {}
                    out = usage.get("outputTokens") or 0
                    dur = d.get("durationMs") or 0
                    rid = d.get("requestId") or ""
                    if out <= 0 or dur <= 0 or not rid:
                        continue
                    records.append({
                        "rid": rid,
                        "started": d.get("startedAt") or "",
                        "turn": d.get("turnId") or "",
                        "model": (d.get("model") or {}).get("modelId") or "unknown",
                        "dur": dur,
                        "out": out,
                        "sub": is_sub,
                    })
        except OSError:
            continue
    records.sort(key=lambda r: r["started"])
    return records


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as fp:
            return json.load(fp)
    except (OSError, json.JSONDecodeError):
        return None


def save_state(seen_rids):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fp:
        json.dump({"seen": seen_rids[-MAX_SEEN:]}, fp)
    os.replace(tmp, STATE_PATH)


def notify(title, body):
    try:
        if sys.platform.startswith("win"):
            _notify_windows(title, body)
        elif sys.platform == "darwin":
            _notify_macos(title, body)
        else:
            _notify_linux(title, body)
    except (OSError, subprocess.SubprocessError):
        pass  # 通知是尽力而为, 平台未授权/无通知服务时静默跳过


def _notify_windows(title, body):
    payload = os.path.join(tempfile.gettempdir(), "zcode-speed-toast-%d.json" % os.getpid())
    with open(payload, "w", encoding="utf-8") as fp:
        json.dump({"title": title, "body": body}, fp, ensure_ascii=False)
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", PS1_PATH, "-Payload", payload],
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    finally:
        try:
            os.remove(payload)
        except OSError:
            pass


def _notify_macos(title, body):
    def applescript_str(s):
        return s.replace("\\", "\\\\").replace('"', '\\"')
    script = 'display notification "%s" with title "%s"' % (
        applescript_str(body), applescript_str(title))
    subprocess.run(["osascript", "-e", script], timeout=15)


def _notify_linux(title, body):
    subprocess.run(["notify-send", title, body], timeout=15)


def main():
    # Stop 触发时最后一条请求可能刚写盘，稍等重扫一次
    records = scan_records()
    if not records:
        time.sleep(0.6)
        records = scan_records()

    state = load_state()
    if state is None:
        save_state([r["rid"] for r in records])
        return 0  # 首次运行只建水位，不弹历史

    seen = set(state.get("seen") or [])
    new = [r for r in records if r["rid"] not in seen]
    all_rids = [r["rid"] for r in records]
    save_state(all_rids)
    if not new:
        return 0

    # 只统计最近一轮对话(主会话最后一条记录所属的 turn)。
    # 积压的历史记录与并行子代理请求静默吸收,避免把多轮/多流混成一条通知。
    main_new = [r for r in new if not r["sub"]]
    if not main_new:
        return 0
    last_turn = main_new[-1]["turn"]
    turn_recs = [r for r in main_new if r["turn"] == last_turn]

    total_out = sum(r["out"] for r in turn_recs)
    if total_out < 10:  # 空回复/心跳类请求不弹
        return 0
    total_dur = sum(r["dur"] for r in turn_recs)
    tps = total_out / (total_dur / 1000.0)

    title = "%s: %.1f tok/s" % (turn_recs[-1]["model"], tps)
    body = "本轮 %d 次模型请求 · %.1fs 生成 · 输出 %s tok" % (
        len(turn_recs), total_dur / 1000.0, format(total_out, ","))
    notify(title, body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
