---
name: speed
description: 查看 ZCode 模型输出速度统计（tokens/sec）。解析本地 rollout 记录，报告每次请求和每个会话的生成速度、耗时与 token 用量。当用户想查看模型输出速度、生成速度、tok/s、token 统计、模型耗时、/speed 时使用。
---

# 模型输出速度统计

运行本技能目录下的 `speed.py`（相对本 SKILL.md 所在目录），分析 `~/.zcode/cli/rollout/` 下 ZCode 记录的每次模型请求数据。脚本只读本地文件，无副作用。

本插件还带一个 Stop hook（`hooks/on_stop.py`）：每次模型回复结束自动弹系统通知（Windows toast / macOS 通知中心 / Linux notify-send），显示本轮的 tok/s。无需手动触发；若用户反馈通知没弹出，检查 `python3`/`python` 是否在 ZCode 进程的 PATH 中，并直接运行该脚本排查。

按用户意图选择参数：

- 查看当前会话速度（默认）: `python speed.py`
- 查看最近 N 条: `python speed.py --last 30`
- 查看全部历史、按模型汇总: `python speed.py --all`
- 指定会话: `python speed.py --session <session-id 前缀>`

规则：

1. 用 `python3`（Linux/macOS）或 `python`/`py`（Windows）执行，工作目录无所谓，脚本按绝对路径定位数据。
2. 脚本输出已是格式化好的中文报告——原样呈现给用户，不要转述或删减表格。
3. 可在报告后补一两句解读（如速度明显偏慢的请求、缓存命中情况），不要重复报告中的数字。
4. 速度口径：输出 token 数 ÷ 流式响应总时长（含思考与工具参数生成），与 API 计费的 outputTokens 一致。
