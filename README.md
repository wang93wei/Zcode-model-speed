# model-speed

ZCode 插件：实时查看模型输出速度（tokens/sec）。无需任何配置，解析 ZCode 本地的请求记录即可统计每次模型调用的生成速度、耗时与 token 用量。

## 功能

- **自动通知**：每次模型回复结束，自动弹系统通知显示这一轮的输出速度
  - Windows：原生 Toast 通知
  - macOS：通知中心（`osascript`，首次使用需授权）
  - Linux：`notify-send`（需 libnotify，主流桌面默认自带）
- **`/speed` 命令**：查看详细报表——最近请求明细、会话汇总、跨会话按模型统计
- **零依赖**：纯 Python 标准库，不需要安装任何第三方包

通知示例：

```
GLM-5.3: 53.5 tok/s
本轮 3 次模型请求 · 27.6s 生成 · 输出 1,723 tok
```

## 安装

### 方式一：从 GitHub 市场安装（推荐）

1. ZCode → **设置 → 插件管理 → Discover** → 点 **`+`** 添加市场
2. 选择 **GitHub repository**，填入：
   ```
   wang93wei/Zcode-model-speed
   ```
3. 在市场列表中找到 **model-speed**，点 **安装**
4. **新开一个对话**生效（hook 在会话启动时注册）

### 方式二：本地安装

1. 克隆本仓库到任意位置：
   ```bash
   git clone https://github.com/wang93wei/Zcode-model-speed.git
   ```
2. ZCode → **设置 → 插件管理 → Discover** → **`+`** → 添加本地文件，选择仓库里的 `marketplace.json`
3. 安装 **model-speed**，新开对话生效

## 使用

安装后自动工作，无需操作：

- **自动通知**：每轮对话结束自动弹出，显示本轮平均输出速度、模型请求次数、生成耗时与输出 token 数
- **`/speed`**：当前会话报表（汇总 + 最近 10 条请求明细）
- **`/speed 最近 30 条`**：查看最近 30 条请求
- **`/speed 全部历史`**：所有会话按模型汇总
- **`/speed 会话 <session-id 前缀>`**：查看指定会话

`/speed` 报表示例：

```
== 会话 model-io-sess_8a02e1da... ==

汇总: 60 次请求 | 总耗时 927.7s | 总输出 40,383 tok | 输入 3,843,904 tok (缓存命中 3,791,040)
  输出速度 tok/s: 加权平均 43.5 | 中位 38.7 | P95 65.1 | 最快 71.4 | 最慢 3.6

时间       | 模型    | 耗时(s) | 输出tok | tok/s
----------------------------------------------------------
08-14 16:53 | GLM-5.3 |    4.8  |     261 |  54.5
08-14 16:53 | GLM-5.3 |   13.5  |     48  |   3.6
```

## 统计口径

- **速度** = 该次响应的输出 token 数 ÷ 流式响应总时长（含思考与工具参数生成），与 API 计费的 `outputTokens` 口径一致
- **一条消息 ≠ 一次模型请求**：ZCode 的 agent 循环中，模型输出 → 调用工具 → 结果回传 → 再输出，每次模型 API 调用记一次。通知里的"本轮 N 次模型请求"按 turnId 分组，只统计你最后一条消息触发的请求
- 并行子代理（subagent）请求不计入通知（避免多流吞吐量混入单流速度），但在 `/speed` 报表中单独标注

## 工作原理

ZCode 在 `~/.zcode/cli/rollout/model-io-*.jsonl` 中记录每次模型请求的完整数据（时长、token 用量、模型信息）。本插件：

- `hooks/on_stop.py` — Stop hook，回复结束时按 requestId 水位增量读取，汇总本轮请求后发送系统通知
- `skills/speed/speed.py` — 解析同样的数据，生成 `/speed` 报表

插件只读本地文件，不联网、不上传任何数据。

## 常见问题

- **通知不弹**：确认 `python3`（或 Windows 上 `python`）在 ZCode 进程的 PATH 中；可手动运行 `python3 hooks/on_stop.py` 排查
- **第一条通知请求数偏多**：插件首次生效会把之前积压的历史请求一次性记入水位，属正常现象，之后每条通知只统计当轮
- **觉得通知频繁**：Windows 可在系统通知设置中将 PowerShell 来源设为"仅通知中心"；或在插件管理中禁用本插件的 hook

## 卸载

设置 → 插件管理 → Installed → model-speed → 卸载。可选清理状态文件 `~/.zcode/cli/model-speed-state.json`。

## 环境要求

- ZCode 客户端
- Python 3.8+（`python3` 或 `python` 任一在 PATH 中）
- Windows / macOS / Linux
