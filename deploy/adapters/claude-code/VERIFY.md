# 迭进 × Claude Code 适配器 验证手册（M2）

> 适配器把 Claude Code hooks 事件翻译为迭进钩子契约 v1 的统一信封，并反译为 Claude hooks 协议响应。
> 本目录代码**只进源码库**；端到端验证需真实 Claude 环境（本机未安装 `claude` CLI）。

## 0. 快速开始（无 Claude 环境时）

```powershell
# 在源码库根目录
python deploy/adapters/claude-code/simulate_test.py
```

预期：`[1] 翻译层` 全部 PASS（PreToolUse deny 翻译 / UserPromptSubmit exit2+stderr / inject / SessionStart 注入），
`[2] 端到端` 5 个事件全部 exit 0。测试走真实 `engine/contract.py`，日志写入 `var/logs/`（已被 gitignore）。

## 1. 安装

### 1.1 安装 Claude Code CLI

```powershell
npm install -g @anthropic-ai/claude-code
claude --version
```

> 建议 CLI 优先：VSCode 扩展下 UserPromptSubmit/PreToolUse 的 additionalContext 注入存在已知 bug
> （claude-code issues #49063 / #20062），CLI 无此问题。

### 1.2 合并 settings

1. 复制 `settings.json.template` 中的 `hooks` 段。
2. 把 `<DGEN_ROOT>` 替换为迭进根目录（含 `engine/contract.py`）。
3. 合并进用户级 `~/.claude/settings.json`（**勿覆盖已有配置**；Claude 会合并多个 hooks 条目），
   或项目级 `.claude/settings.json`（仅该项目生效）。
4. 验证配置被识别：`claude` 启动后执行 `claude doctor`（hooks 一节应列出已注册命令）。

### 1.3 事件映射（契约 → Claude）

| 契约事件 | Claude 事件 | matcher | 适配器脚本 |
|---|---|---|---|
| `session_start` | `SessionStart` | `startup\|resume` | `diegin_claude_session_start.py` |
| `prompt_pre` | `UserPromptSubmit` | （默认全部） | `diegin_claude_prompt.py` |
| `tool_pre` | `PreToolUse` | `.*` | `diegin_claude_pre_tool.py` |
| `tool_post` | `PostToolUse` | `.*` | `diegin_claude_post_tool.py` |
| `stop` | `Stop` | `always` | `diegin_claude_stop.py` |
| （可选） | `PreCompact` | （默认全部） | `diegin_claude_stop.py` |

## 2. 验证点

### 2.1 SessionStart 注入

- 启动 `claude`（新会话 `startup` 或 `resume`）。
- 首轮 prompt 前，模型上下文应含「[迭进] 全域常驻自我迭代进化系统已激活」及引擎健康摘要
  （`total_rules` / `active_rules` / entropy / snr / satisfaction）。

### 2.2 PreToolUse 预检与阻断

- 正常工具调用：迭进审计日志出现 `task_type=pre_tool` 检查记录，工具正常执行。
- 触发迭进规则命中（如破坏性命令/受保护文件）：stdout 应返回
  `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"[迭进] ..."}}`，
  Claude 拒绝执行该工具并向用户展示 reason。
- 注意：PreToolUse 阻断必须用 `exit 0` + deny JSON（M2 采用官方现代语义）；
  `exit 2` 在 PreToolUse 会被当作 hook 崩溃而忽略（claude-code issues #37210 / #43407）。

### 2.3 UserPromptSubmit 预检与注入

- 每轮提问：迭进 `pre_reply` 检查执行；命中攻七推荐时，stdout 返回
  `{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"..."}}`，推荐进入会话上下文。
- 阻断：脚本 `exit 2` + stderr 回显阻断提示（UserPromptSubmit 的可靠阻断通道），模型回复前提示用户。

### 2.4 PostToolUse / Stop / PreCompact

- 工具执行后：审计日志出现 `tool_post` 健康上报记录。
- 会话结束：审计日志出现 `stop` 确认记录（契约层 acknowledged）。
- 上下文压缩时：`PreCompact` 复用 stop 适配器，同样留痕。

## 3. 故障排查

| 现象 | 排查 |
|---|---|
| hooks 未触发 | `claude doctor` 检查配置；确认 matcher 正确（SessionStart 需 `startup\|resume`，Stop 需 `always`） |
| PreToolUse 不阻断 | 确认脚本 stdout 是单行 JSON 且 `exit 0`；检查规则是否真的命中（看审计日志 matched_count） |
| 注入内容乱码 | 确认系统 Python 为 3.7+（`reconfigure` 可用）；适配器已强制 stdout UTF-8 |
| 引擎异常但业务被放行 | 这是设计（fail-open）：契约层异常返回 allow 并标注 error；审计日志有 `ENGINE_ERROR` 字样 |
| 找不到 contract.py | 设置环境变量 `DGEN_ROOT` 指向迭进根，或检查 `<DGEN_ROOT>` 替换是否正确 |

## 4. 纪律

- 本目录适配器为纯 Python：UTF-8 NoBOM + LF（与 PS1 钩子的 BOM 要求不同）。
- 代码不含本机绝对路径：迭进根默认按 `__file__` 相对定位（上 3 级），可用 `DGEN_ROOT` 覆盖。
- 引擎/契约异常一律 fail-open：不因迭进故障阻断用户业务。
- 审计口径：所有事件在契约层统一留痕 `var/logs/diegin_audit.log`。