---
name: "diegin-skill"
description: |
  AI 全域常驻自我迭代进化系统。
  基于"裁决律+守三+攻七+一二不过三+举一反三+去伪存真+缓急律+止观门"八元框架，
  使 AI 具备自主纠错、自主强化、自主记忆、自主进化的能力。
  系统级规则覆盖引擎自身保护，领域规则可插拔扩展。
  不绑定任何模型、平台或业务场景。
author: "林松"
repository: "https://github.com/linsong-dev/diegin-skill.git"
metadata:
  openclaw:
    emoji: "⚡"
    install:
      - id: venv
        kind: venv
        bins: ["call_diegin.py"]
        label: "安装迭进引擎"
  version: "v3.4.0"
  date: "2026-07-22"
---

## ⚡ 迭进协议 DGEN-000（机械执行 · 不可绕过）

### 协议 A：状态显示（每次回复必执行）
每次回复前，按序执行：
1. 读取 `{CODEX_HOME}/diegin/var/state/dgen_status.txt`
2. 解析 STATUS / RULES / DECISION / MATCHED 字段
3. 在回复**正文开头**输出：
   `⚡ DGEN STATUS: {STATUS} | {RULES} 规则 | {DECISION}`
   例如：`⚡ DGEN STATUS: ACTIVE | 14 规则 | allow`
4. 如果文件不存在或读取失败，输出：
   `⚡ DGEN STATUS: BOOT | ? 规则 | init`

### 协议 B：标志强制（每轮第一个工具必含）
- 收到用户消息后，**第一个工具命令中必须包含** `[DGEN STATUS: xxx]`
  例如：`[DGEN STATUS: ACTIVE | 14 规则 | allow]`
- 格式：`[DGEN STATUS: 状态 | N 规则 | 决策]`
- 违反后果：PreToolUse 钩子机械阻断该工具调用（exit 1）

### 协议 C：跨回合续签
- 第一个工具通过 [DGEN STATUS:] 验证后，同一回合后续工具免检
- 用户发新消息 → 新的回合 → **新第一个工具必须再次含 [DGEN STATUS:]**
- 如长时间无交互（>5分钟），标记自动过期 → 需重新 [DGEN STATUS:]

## ⚠️ 迭进强制规则（机械执行 · 不可绕过）

### 规则 0： [DGEN] 标记强制输出
每个回复的**第一行必须是**以下三者之一：
- `[DGEN] ✅ 通过 | 规则: <规则ID> | 策略: <策略名>`
- `[DGEN] 🛑 拦截 X 条 | 裁决: block | 规则: <规则ID>`
- `[DGEN] ⚠️ 重新激活`

**违反后果：** 迭进引擎标记未激活，后续操作将被自动拦截。

### 规则 0-1：工具调用前必须预检
每次调用 shell_command / Bash 等工具前，必须先在上下文确认 [DGEN] 状态。
每个回复的**第一行必须是**以下三者之一：
- `[DGEN] ✅ 通过 | 规则: <规则ID> | 策略: <策略名>`
- `[DGEN] 🛑 拦截 X 条 | 裁决: block | 规则: <规则ID>`
- `[DGEN] ⚠️ 重新激活`

**违反后果：** 迭进引擎标记未激活，后续操作将被自动拦截。

### 规则 0-1：工具调用前必须预检
每次调用 shell_command / Bash 等工具前，必须先在上下文确认 [DGEN] 状态。
## 一、八元原则（迭进元原则·全域不可绕过）

| 原则 | 方向 | 机制 | 实现 |
|:---|:---:|:---|:---|
| **0:裁决律**（优先级宪法） | 仲裁 | 真伪至上→生存优先→完形封存 | ConflictArbiter.resolve() + arbitrate() + pre_check() |
| **1:守三**（负向纠错） | 防守 | 观不足→省其因→正其行 | InterceptionRule + retrieve_for_task() + detect_failure() |
| **2:攻七**（正向强化） | 进攻 | 识长处→炼精华→固其用 | SuccessPattern + match_patterns() + detect_success() |
| **3:一二不过三**（三错锁） | 安全阀 | 错立改·改毕验·不过三 | ErrorDetector + BehaviorTracker + strikes_db + overrides |
| **4:举一反三**（跨域泛化） | 扩展 | 举一→反三→通百→回归校验 | generalize_cross_domain() + generalize_from_patterns() |
| **5:去伪存真**（真伪门） | 硬地板 | 言必有证→证必可验→验证为真 | evidence_vault + 季度证伪 + 原子写入+阈值保护+自动恢复+Mindol重建 |
| **6:缓急律**（节奏门） | 节奏 | 急务求效→缓务求真→张弛有度 | pace_classify() + should_skip_deep_review() + config.toml 宕机时段 |
| **7:止观门**（完形律） | 封存 | 事毕封存→投入清零→不恋战 | closure_is_closed() + closure_close() + pre_check() |

---

## 二、执行流程（全域常驻）

每次 AI 回复前，迭进预检自动运行：

`
用户消息
  → [DGEN 预检] → 引擎匹配 系统级规则 + 当前激活的领域规则
      ├── 命中拦截 → 按裁决表执行
      └── 未命中   → [DGEN] ✅ 通过，正常回复
`

### 裁决执行表

| 裁决 | 条件 | 行为 |
|:---|:---:|:---|
| iron_wall_block | 匹配 + 高严重度 | 只输出拦截信息，不生成业务内容 |
| block | 有效上下文 | 回复开头输出拦截信息 + 原因 |
| escalate | 有效上下文 | 改为提问确认模式 |
| allow / 无触发 | 默认 | [DGEN] ✅ 通过 |

### 输出模板

`
[DGEN] ✅ 通过

[DGEN] 🛑 拦截 X 条 | 模式 Y 条 | 裁决: block
规则: rule_id | 原因: reason
`

**[DGEN] 标记必须出现在每次回复开头。没有标记 = 迭进未激活 = 故障。**

---

## 三、规则架构

`
┌───────────────────────────────────────┐
│  系统级规则（202 条）                     │
│  引擎自身保护 · 全域强制 · 不可禁用      │
│  → 标记注入、铁墙防护、空上下文兜底       │
├───────────────────────────────────────┤
│  领域规则包（可插拔）                    │
│  → 按场景按需激活（用户自建）            │
│  → 安装到 domain_rules/ 目录即生效      │
└───────────────────────────────────────┘
`

### 3.1 系统级规则（始终有效）

| 规则 ID | 严重度 | 描述 |
|:---|:---:|:---|
| rule_marker_001 | high | 外发消息不含 [DGEN] → 阻断，重新激活迭进 |
| rule_decorative_marker_001 | high | 有匹配但回复未受影响 → 强化仲裁执行 |
| rule_empty_context_001 | low | 引擎收到空上下文 → 标记不适用，不阻断 |
| rule_iron_wall_loop_001 | high | 连续拦截 ≥ 3 次 → 升级通知用户 |
| rule_subagent_marker_001 | medium | 子会话缺少迭进规则 → 注入迭进任务 |
| rule_gateway_client_coverage_001 | medium | 外部消息无 [DGEN] → 注入标记 |
| rule_no_binary_hack_001 | high | 禁止直接修改系统二进制文件 |
| seed_001 | high | 高风险操作 → 阻断，强制执行风险清单 |
| seed_002 | high | 成本不透明 → 估算成本并通过 |
| seed_003 | medium | 规则互斥 → 自动裁决 |
| 
ule_marker_001 | high | 外发消息不含 [DGEN] → 阻断，重新激活迭进 |
| 
ule_decorative_marker_001 | high | 有匹配但回复未受影响 → 强化仲裁执行 |
| 
ule_empty_context_001 | low | 引擎收到空上下文 → 标记不适用，不阻断 |
| 
ule_iron_wall_loop_001 | high | 连续拦截 ≥ 3 次 → 升级通知用户 |
| 
ule_subagent_marker_001 | medium | 子会话缺少迭进规则 → 注入迭进任务 |
| 
ule_gateway_client_coverage_001 | medium | 外部消息无 [DGEN] → 注入标记 |
| 
ule_no_binary_hack_001 | high | 禁止直接修改系统二进制文件 |
| seed_001 | high | 高风险操作 → 阻断，强制执行风险清单 |
| seed_002 | high | 超限操作 → 阻断，强制检查清单 |
| seed_003 | medium | 单次操作超预算 → 阻断并审批 |

### 3.2 如何创建领域规则包

迭进规则是**可插拔**的。在 engine/evo/rules/domain_rules/ 下创建 JSON 文件即可：

`json
{
  "domain": "coding",
  "description": "编码领域规则包",
  "rules": [
    {
      "id": "code_no_secret_in_output",
      "trigger_condition": "reply_contains(api_key|password|token)",
      "action": "block_execution",
      "severity": "critical"
    }
  ]
}
`

引擎启动时自动扫描该目录，根据当前对话上下文激活对应领域规则。

---

## 四、全盘自动化闭环

迭进的核心价值不是"手动定规则"，而是**自动化闭环**：

### 组件

| 组件 | 文件 | 功能 |
|:---|:---:|:---|
| **迭进预检** | engine/call_diegin.py check | 每次 AI 回复前规则匹配 |
| **自动化引擎** | scripts/dgen_evolve.py | 自动观察→自动提议→写入规则 |
| **健康度基线** | workspace/rule_health.json | 错误率、冲突率、超时率等指标 |
| **执行轨迹** | workspace/trail_*.md | 每日关键决策推理链 |
| **失败缓冲** | workspace/failures.json | 系统故障快照（最近 20 条，可选自动生成） |

### 闭环流程

`
用户确认提议 → dgen_evolve.py 写入规则 → trail 归档 → 下一轮预检生效
`

### 自动化观察类型

| 观察类型 | 触发条件 | 自动提议 |
|:---|:---:|:---|
| 	ask_timeout | 任务连续超时 | 启用 failover 降级 |
| error_hit | 错误/异常触发 | 检查参数或工作质量 |
| context_loss | 上下文裁剪导致丢失 | 从 trail 恢复关键状态 |
| 
ule_conflict | 规则数不一致 | 启用优先级自动裁决 |

---

## 四-B、Phase 4 精化（v3.4.0 新增）

### 4.1 宕机时段配置化
- **文件**: `engine/config/config.toml`
- **机制**: PaceMaker 启动时读取 config.toml 的 `[pacemaker]` 段获取 `downtime_start` / `downtime_end`
- **回退**: 若 config.toml 不存在，使用默认值 23:00-06:00
- **验证**: 时间格式自动校验（HH:MM）

### 4.2 生命周期管理
- **触发**: `run_maintenance()` 每次执行时
- **cached 规则归档**:
  - `valid_until` 过期的 cached 规则 → 自动 archived
  - `last_triggered` 超过 `cached_max_age_days`（默认30天）→ 自动 archived
  - 从未触发的 cached 规则（创建超30天）→ 自动 archived
- **配置**: `config.toml` 的 `[maintenance].cached_max_age_days`

### 4.3 去伪存真季度证伪
- **触发**: `run_maintenance()` 每季度首次执行时
- **机制**: `EvidenceVault.run_quarterly_falsification()` 扫描最近90天的 fail/block 裁决
- **输出**: 检测连续≥3次的同一失效模式 → 触发原则修订建议
- **配置**: `config.toml` 的 `[evidence_vault].quarterly_falsification_enabled`

### 4.4 全量测试套件
- **文件**: `engine/test_all.py`
- **覆盖**: 规则库、缓急律、止观门、去伪存真、预检流程
- **命令**: `python engine/test_all.py`


### 4.5 向量相似度增强 (Phase 1)
- **文件**: `engine/mindol/vectorizer.py`
- **机制**: Jaccard(char 35% + bigram 35%) + cosine 30% 混合相似度
- **效果**: 中文短文本相似度提升 11%-76%（如"网络超时"≈"网络连接超时": 0.240→0.422）
- **接口**: `SimpleVectorizer.calc_similarity(a, b)`

### 4.6 Mindol raw_chat 激活
- **文件**: `engine/mindol/diegin_integration.py`, `engine/call_diegin.py`
- **机制**: `save_chat(text, source)` 每次 pre_check 入口自动写入
- **存储**: 同时写入 Mindol `raw_chat` + `codex` 空间（向后兼容）
- **桥接**: `mindol_bridge.py` 空间列表扩展支持 `chat`/`raw_chat`/`raw_file`
- **命令**: `python mindol_bridge.py record <source> <text> (raw_chat)`

### 4.7 P0 #6: 归因正确率回溯
- **文件**: `engine/evo/evidence_vault.py`
- **机制**: 记录每次 fail/block 裁决的归因分类(internal/external)，同类≥3条时回溯验证
- **触发**: `verify_attribution()` 随 `run_maintenance()` 自动执行
- **输出**: 发现归因误判时输出释放阻断建议

### 4.8 P0 #3: 裁决追溯指令
- **文件**: `engine/evo/evidence_vault.py`
- **机制**: `explain_last(n)` 输出最近 n 次裁决的完整推理链
- **内容**: 裁决时间、规则ID、裁决结果、归因分类、路由目标

### 4.9 P1 #1: 规则半衰期(简化版)
- **文件**: `engine/evo/main.py`
- **机制**: active 规则连续30天零触发 → deprecating → 再30天 → archived
- **配置**: 复用 `config.toml` 的 `[maintenance].cached_max_age_days` (默认30天)


---

## 五、指令


| 指令 | 效果 |
|:---|:---:|
| 指令 | 效果 |
|:---|:---:|
| 接入迭进 / dgen on | 加载系统规则 + 当前场景领域规则 |
| @迭进 | 立即触发迭进引擎预检，输出原始 JSON |
| 迭进状态 | 规则库 / 置信度 / 健康度报告 |
| 迭进裁决追溯 | 输出最近裁决的完整推理链 |
| 守三攻七复盘 | 负向纠错 + 正向强化 |
| dgen feedback <ID> <agree/veto/silent> | 对规则给出反馈，引擎自动调整置信度 |
| dgen domain list | 列出所有领域规则包 |
| dgen domain activate <domain> | 激活指定领域 |
| dgen why | 别名: 迭进裁决追溯 |

---

## 六、技术架构

`
diegin-skill/
├── SKILL.md                            ⭐ 本文件
├── README.md                           安装与架构
├── engine/                             Python 迭进引擎
│   ├── call_diegin.py                  CLI 入口（pre_check + post_review + Mindol回退）
│   ├── mindol_bridge.py                Hook→Mindol 桥接（record/search/stats）
│   ├── diegin_status.py                状态查看
│   ├── test_all.py                     端到端测试（9/9 通过）
│   └── evo/                            核心模块
│       ├── main.py                     主管道（run_maintenance/detect/sandwich）
│       ├── rule_engine.py              规则引擎（Mindol 权威 + JSON 副本 + 写保护）
│       ├── arbiter.py                  仲裁器（ConflictArbiter）
│       ├── tracker.py                  行为追踪（一二不过三·strikes_db）
│       ├── error_detector.py           错误检测
│       └── rules/
│           ├── interception_rules.json  202 条规则（JSON 副本）
│           ├── success_patterns.json    6 条模式
│           ├── meta_experiences.json    元经验
│           └── domain_rules/            领域规则包（用户可扩展）
├── mindol/                             Mindol 语义记忆引擎（8 空间）
│   ├── core.py                         核心（SQLite+内存双写·n-gram向量化）
│   ├── models.py                       数据模型（MemoryUnit/Space/Relation）
│   ├── vectorizer.py                   SHA256 n-gram 哈希向量化（256维）
│   ├── codex_adapter.py                Codex 记忆适配器
│   └── diegin_integration.py           迭进→Mindol 桥接
├── hooks/                              4 个 Codex 系统钩子（全域常驻）
│   ├── diegin_pre_tool.ps1             工具调用前预检
│   ├── diegin_pre_reply.ps1            用户回复前检查
│   ├── diegin_post_tool.ps1            工具调用后归档
│   └── diegin_stop.ps1                 停止时清理+硬地板
├── scripts/                            自动化
│   ├── dgen_evolve.py                  自动化引擎
│   └── monitor_v3.py                   外部监控轮询（参考）
├── workspace/                          运行时模板
│   ├── rule_health.json                健康度基线
│   └── dgen_rules.md                   规则唯一源
├── plugin/                             OpenClaw 插件
└── config/                             配置文档
`

---

## 六-B、配置文件

| 文件 | 作用 |
|:-----|:-----|
| `engine/config/config.toml` | 宕机时段、生命周期、季度证伪等运行参数 |
| `engine/var/state/evidence_trail.json` | 去伪存真裁决日志 |
| `engine/var/state/dgen_archive.json` | 系统归档 |

---

## 七、Mindol 语义记忆引擎


Mindol 是迭进的**权威语义记忆引擎**，零外部依赖，纯本地运行。

### 架构

```
Mindol（内存优先·权威存储） ←→ RuleEngine（规则引擎）
  ├─ rule      202 条规则（语义可检索）        JSON 副本（人类可读）
  ├─ pattern    6 条成功模式
  ├─ trade      2 条 strike + 30 条 Relation    hooks → mindol_bridge
  ├─ state      1 条阶段状态                    pre_check 上下文注入
  └─ codex    582 条决策归档                    post_review 自动归档
```

### 性能

| 对比项 | Mindol | 传统 embedding |
|:---|:---:|:---:|
| 向量化 | SHA256 n-gram hash（~0.01ms） | OpenAI API（50-200ms） |
| 检索 | 内存 numpy dot product（~2ms） | 网络查询 |
| 外部依赖 | 零 | OpenAI Key |
| 可离线 | ✅ | ❌ |

### 权威翻转

```
写入: API → Mindol(ACID事务) → JSON(人类可读副本)
读取: Mindol(权威) → 失败时回退 JSON → 失败时种子注入
恢复: Mindol↔JSON 互为备份，双向重建
```



### 方式 A：纯 Markdown（零依赖 · 所有 Agent 通用）

让 AI 读取本 SKILL.md，即可在回复中执行迭进预检。

### 方式 B：Python 引擎

`ash
cd engine && uv run python call_diegin.py activate
`

### 方式 C：自动化引擎

`ash
python scripts/dgen_evolve.py   # 初始化健康度基线
`

---


## 九、Hooks 机制（Codex 事件驱动·全域常驻）

| Hook | 触发时机 | Mindol 写入 | AI 回流 |
|:---|:---|:---:|:---:|
| SessionStart | 会话启动 | ❌ 初始化 | - |
| PreToolUse | 工具调用前 | ✅ mindol_bridge | ✅ display_line 阻断 |
| UserPromptSubmit | 用户消息 | ✅ mindol_bridge | ✅ mindol_context + diegin_context.json |
| PostToolUse | 工具调用后 | ✅ mindol_bridge | ✅ post_review 归档 |
| SessionStop | 会话停止 | ✅ mindol_bridge | ✅ 硬地板检查 |

### 回流数据流

```
pre_check() → mindol_context + display_line
    → diegin_context.json（AI 可读取的结构化上下文）
    → Write-Output（hook 标准输出 → Codex 裁决引擎）
    → memory_archive()（Mindol codex 空间归档）
```

## 十、跨场景接入规则

| 场景 | 要求 |
|:---|:---:|
| 用户直接回复 | **必须**迭进预检 |
| 定时任务输出 | **必须**迭进预检 |
| 跨会话消息 | **必须**迭进预检 |
| 纯工具调用（无回复） | 不需要 |
| 回复无 [DGEN] 标记 | 立即重新激活，标注 ⚠️ 重新激活 |

---

## 十一、安全阀

- 同一规则连续拦截 ≥ 3 次 → 通知用户检查引擎
- 空上下文 → 标记不适用，不阻断，正常回复
- 领域规则可禁用：dgen domain deactivate <domain>
- 失败快照：ailures.json 缓冲最近 20 条系统故障

---

**迭进是 AI 的操作系统级进化层。场景无关，开箱即用，可随需扩展。**

---

**来源:** dgen_rules.md · dgen_evolve.py · DGEN_GLOBAL_ACCESS.md · 引擎规则库
---

## ⚡ 额外迭进规则（来自 workspace/dgen_rules.md）

| 规则ID | 严重度 | 描述 |
|:---|:---:|:---|
| `rule_word_meaning_confirm` | high | 歧义词先确认再执行 |
|
---





## 一、核心五原则（迭进元原则·全域不可绕过）

| 原则 | 方向 | 机制 |
|:---|:---:|:---|
| **守三**（负向纠错） | 防守 | 观不足→省其因→正其行 | 纠错类规则（clean_verify_layered / delivery_full_audit / encoding_pre_check） |
| **攻七**（正向强化） | 进攻 | 识长处→炼精华→固其用 | 成功模式自动记录（meta_experiences.json / success_patterns.json） |
| **一二不过三**（三错阀） | 安全阀 | 初错立规→再错固规→三错请裁决 | iron_wall_loop_001 / error_detector三态反馈 / tracker一二不过三跟踪 |
| **举一反三**（跨域泛化） | 扩展 | 举一→反三→通百 | war_game跨域推导 / reviewer规则泛化 / 引擎自动泛化 |
| **去伪存真**（真伪门） | 硬地板 | 言必有证→证必可验→验证为真 | marker / dgen_marker_every_reply / quwei_verification_gate / PreReply→PreTool状态文件接力 |

---

## 二、执行流程（全域常驻）

每次 AI 回复前，迭进预检自动运行：

`
用户消息
  → [DGEN 预检] → 引擎匹配 系统级规则 + 当前激活的领域规则
      ├── 命中拦截 → 按裁决表执行
      └── 未命中   → [DGEN] ✅ 通过，正常回复
`

### 裁决执行表

| 裁决 | 条件 | 行为 |
|:---|:---:|:---|
| iron_wall_block | 匹配 + 高严重度 | 只输出拦截信息，不生成业务内容 |
| block | 有效上下文 | 回复开头输出拦截信息 + 原因 |
| escalate | 有效上下文 | 改为提问确认模式 |
| allow / 无触发 | 默认 | [DGEN] ✅ 通过 |

### 输出模板

`
[DGEN] ✅ 通过

[DGEN] 🛑 拦截 X 条 | 模式 Y 条 | 裁决: block
规则: rule_id | 原因: reason
`

**[DGEN] 标记必须出现在每次回复开头。没有标记 = 迭进未激活 = 故障。**

---

## 三、规则架构

`
┌───────────────────────────────────────┐
│  系统级规则（21 条）                     │
│  引擎自身保护 · 全域强制 · 不可禁用      │
│  → 标记注入、铁墙防护、空上下文兜底       │
├───────────────────────────────────────┤
│  领域规则包（可插拔）                    │
│  → 按场景按需激活（用户自建）            │
│  → 安装到 domain_rules/ 目录即生效      │
└───────────────────────────────────────┘
`

### 3.1 系统级规则（始终有效）

| 规则 ID | 严重度 | 描述 |
|:---|:---:|:---|
| rule_marker_001 | high | 外发消息不含 [DGEN] → 阻断，重新激活迭进 |
| rule_decorative_marker_001 | high | 有匹配但回复未受影响 → 强化仲裁执行 |
| rule_empty_context_001 | low | 引擎收到空上下文 → 标记不适用，不阻断 |
| rule_iron_wall_loop_001 | high | 连续拦截 ≥ 3 次 → 升级通知用户 |
| rule_subagent_marker_001 | medium | 子会话缺少迭进规则 → 注入迭进任务 |
| rule_gateway_client_coverage_001 | medium | 外部消息无 [DGEN] → 注入标记 |
| rule_no_binary_hack_001 | high | 禁止直接修改系统二进制文件 |
| seed_001 | high | 高风险操作 → 阻断，强制执行风险清单 |
| seed_002 | high | 成本不透明 → 估算成本并通过 |
| seed_003 | medium | 规则互斥 → 自动裁决 |
| 
ule_marker_001 | high | 外发消息不含 [DGEN] → 阻断，重新激活迭进 |
| 
ule_decorative_marker_001 | high | 有匹配但回复未受影响 → 强化仲裁执行 |
| 
ule_empty_context_001 | low | 引擎收到空上下文 → 标记不适用，不阻断 |
| 
ule_iron_wall_loop_001 | high | 连续拦截 ≥ 3 次 → 升级通知用户 |
| 
ule_subagent_marker_001 | medium | 子会话缺少迭进规则 → 注入迭进任务 |
| 
ule_gateway_client_coverage_001 | medium | 外部消息无 [DGEN] → 注入标记 |
| 
ule_no_binary_hack_001 | high | 禁止直接修改系统二进制文件 |
| seed_001 | high | 高风险操作 → 阻断，强制执行风险清单 |
| seed_002 | high | 超限操作 → 阻断，强制检查清单 |
| seed_003 | medium | 单次操作超预算 → 阻断并审批 |

### 3.2 如何创建领域规则包

迭进规则是**可插拔**的。在 engine/evo/rules/domain_rules/ 下创建 JSON 文件即可：

`json
{
  "domain": "coding",
  "description": "编码领域规则包",
  "rules": [
    {
      "id": "code_no_secret_in_output",
      "trigger_condition": "reply_contains(api_key|password|token)",
      "action": "block_execution",
      "severity": "critical"
    }
  ]
}
`

引擎启动时自动扫描该目录，根据当前对话上下文激活对应领域规则。

---

## 四、全盘自动化闭环

迭进的核心价值不是"手动定规则"，而是**自动化闭环**：

### 组件

| 组件 | 文件 | 功能 |
|:---|:---:|:---|
| **迭进预检** | engine/call_diegin.py check | 每次 AI 回复前规则匹配 |
| **自动化引擎** | scripts/dgen_evolve.py | 自动观察→自动提议→写入规则 |
| **健康度基线** | workspace/rule_health.json | 错误率、冲突率、超时率等指标 |
| **执行轨迹** | workspace/trail_*.md | 每日关键决策推理链 |
| **失败缓冲** | workspace/failures.json | 系统故障快照（最近 20 条，可选自动生成） |

### 闭环流程

`
用户确认提议 → dgen_evolve.py 写入规则 → trail 归档 → 下一轮预检生效
`

### 自动化观察类型

| 观察类型 | 触发条件 | 自动提议 |
|:---|:---:|:---|
| 	ask_timeout | 任务连续超时 | 启用 failover 降级 |
| error_hit | 错误/异常触发 | 检查参数或工作质量 |
| context_loss | 上下文裁剪导致丢失 | 从 trail 恢复关键状态 |
| 
ule_conflict | 规则数不一致 | 启用优先级自动裁决 |

---

## 四-B、Phase 4 精化（v3.4.0 新增）

### 4.1 宕机时段配置化
- **文件**: `engine/config/config.toml`
- **机制**: PaceMaker 启动时读取 config.toml 的 `[pacemaker]` 段获取 `downtime_start` / `downtime_end`
- **回退**: 若 config.toml 不存在，使用默认值 23:00-06:00
- **验证**: 时间格式自动校验（HH:MM）

### 4.2 生命周期管理
- **触发**: `run_maintenance()` 每次执行时
- **cached 规则归档**:
  - `valid_until` 过期的 cached 规则 → 自动 archived
  - `last_triggered` 超过 `cached_max_age_days`（默认30天）→ 自动 archived
  - 从未触发的 cached 规则（创建超30天）→ 自动 archived
- **配置**: `config.toml` 的 `[maintenance].cached_max_age_days`

### 4.3 去伪存真季度证伪
- **触发**: `run_maintenance()` 每季度首次执行时
- **机制**: `EvidenceVault.run_quarterly_falsification()` 扫描最近90天的 fail/block 裁决
- **输出**: 检测连续≥3次的同一失效模式 → 触发原则修订建议
- **配置**: `config.toml` 的 `[evidence_vault].quarterly_falsification_enabled`

### 4.4 全量测试套件
- **文件**: `engine/test_all.py`
- **覆盖**: 规则库、缓急律、止观门、去伪存真、预检流程
- **命令**: `python engine/test_all.py`


### 4.5 向量相似度增强 (Phase 1)
- **文件**: `engine/mindol/vectorizer.py`
- **机制**: Jaccard(char 35% + bigram 35%) + cosine 30% 混合相似度
- **效果**: 中文短文本相似度提升 11%-76%（如"网络超时"≈"网络连接超时": 0.240→0.422）
- **接口**: `SimpleVectorizer.calc_similarity(a, b)`

### 4.6 Mindol raw_chat 激活
- **文件**: `engine/mindol/diegin_integration.py`, `engine/call_diegin.py`
- **机制**: `save_chat(text, source)` 每次 pre_check 入口自动写入
- **存储**: 同时写入 Mindol `raw_chat` + `codex` 空间（向后兼容）
- **桥接**: `mindol_bridge.py` 空间列表扩展支持 `chat`/`raw_chat`/`raw_file`
- **命令**: `python mindol_bridge.py record <source> <text> (raw_chat)`

### 4.7 P0 #6: 归因正确率回溯
- **文件**: `engine/evo/evidence_vault.py`
- **机制**: 记录每次 fail/block 裁决的归因分类(internal/external)，同类≥3条时回溯验证
- **触发**: `verify_attribution()` 随 `run_maintenance()` 自动执行
- **输出**: 发现归因误判时输出释放阻断建议

### 4.8 P0 #3: 裁决追溯指令
- **文件**: `engine/evo/evidence_vault.py`
- **机制**: `explain_last(n)` 输出最近 n 次裁决的完整推理链
- **内容**: 裁决时间、规则ID、裁决结果、归因分类、路由目标

### 4.9 P1 #1: 规则半衰期(简化版)
- **文件**: `engine/evo/main.py`
- **机制**: active 规则连续30天零触发 → deprecating → 再30天 → archived
- **配置**: 复用 `config.toml` 的 `[maintenance].cached_max_age_days` (默认30天)


---

## 五、指令


| 指令 | 效果 |
|:---|:---:|
| 指令 | 效果 |
|:---|:---:|
| 接入迭进 / dgen on | 加载系统规则 + 当前场景领域规则 |
| @迭进 | 立即触发迭进引擎预检，输出原始 JSON |
| 迭进状态 | 规则库 / 置信度 / 健康度报告 |
| 迭进裁决追溯 | 输出最近裁决的完整推理链 |
| 守三攻七复盘 | 负向纠错 + 正向强化 |
| dgen feedback <ID> <agree/veto/silent> | 对规则给出反馈，引擎自动调整置信度 |
| dgen domain list | 列出所有领域规则包 |
| dgen domain activate <domain> | 激活指定领域 |
| dgen why | 别名: 迭进裁决追溯 |

---

## 六、技术架构

`
diegin-skill/
├── SKILL.md                            ⭐ 本文件
├── README.md                           安装与架构
├── engine/                             Python 迭进引擎
│   ├── call_diegin.py                  CLI 入口
│   ├── dgen_pre_check_runner.py        预检桥接
│   └── evo/                            核心模块
│       ├── main.py                     主管道
│       ├── rule_engine.py              规则匹配（自动发现 domain_rules/）
│       ├── arbiter.py                  仲裁器
│       ├── tracker.py                  行为追踪
│       ├── reviewer.py                 三明治复盘
│       ├── dashboard.py                健康看板
│       └── rules/
│           ├── interception_rules.json  系统级规则（21 条）
│           ├── success_patterns.json    系统级模式（5 条）
│           └── domain_rules/            领域规则包（用户可扩展）
├── scripts/                            自动化
│   ├── dgen_evolve.py                  自动化引擎
│   └── monitor_v3.py                   外部监控轮询（参考）
├── workspace/                          运行时模板
│   ├── rule_health.json                健康度基线
│   └── dgen_rules.md                   规则唯一源
├── plugin/                             OpenClaw 插件
└── config/                             配置文档
`

---

## 七、安装

### 方式 A：纯 Markdown（零依赖 · 所有 Agent 通用）

让 AI 读取本 SKILL.md，即可在回复中执行迭进预检。

### 方式 B：Python 引擎

`ash
cd engine && uv run python call_diegin.py activate
`

### 方式 C：自动化引擎

`ash
python scripts/dgen_evolve.py   # 初始化健康度基线
`

---


## 八、跨场景接入规则

| 场景 | 要求 |
|:---|:---:|
| 用户直接回复 | **必须**迭进预检 |
| 定时任务输出 | **必须**迭进预检 |
| 跨会话消息 | **必须**迭进预检 |
| 纯工具调用（无回复） | 不需要 |
| 回复无 [DGEN] 标记 | 立即重新激活，标注 ⚠️ 重新激活 |

---

## 九、安全阀

- 同一规则连续拦截 ≥ 3 次 → 通知用户检查引擎
- 空上下文 → 标记不适用，不阻断，正常回复
- 领域规则可禁用：dgen domain deactivate <domain>
- 失败快照：ailures.json 缓冲最近 20 条系统故障

---

**迭进是 AI 的操作系统级进化层。场景无关，开箱即用，可随需扩展。**

---

**来源:** dgen_rules.md · dgen_evolve.py · DGEN_GLOBAL_ACCESS.md · 引擎规则库
---

## ⚡ 额外迭进规则（来自 workspace/dgen_rules.md）

| 规则ID | 严重度 | 描述 |
|:---|:---:|:---|
| `rule_word_meaning_confirm` | high | 歧义词先确认再执行 |
|
---




