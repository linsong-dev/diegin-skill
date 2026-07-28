---
name: "diegin-skill"
description: |
  Diegin（迭进）— 系统级认知框架。基于八元原则网络（裁决律·守三+攻七+一二不过三+举一反三+去伪存真+缓急律+止观门），
  通过运行时钩子全域常驻 AI 执行循环，使 AI 具备自主纠错、自主强化、自主记忆、自主进化的能力。
  引擎层提供规则仲裁与强制阻断，记忆层提供跨会话持久语义存储。
  不绑定任何模型、平台或业务场景，以插件形式寄生运行，不可降级为纯文档技能。
author: "林松"
repository: "https://github.com/linsong-dev/diegin-skill.git"
metadata:
  version: "v3.4.0"
  date: "2026-07-22"
---

## ⚡ Diegin（迭进）— 系统级认知框架

### 身份
一个具有独立架构的系统级认知框架，通过 Codex 插件机制分发和寄生运行，不可降级为纯文档技能。

### 层级结构
| 层 | 组件 | 职责 |
|:--|:----|:----|
| **认知层** | 八元原则网络 | 核心逻辑 |
| **引擎层** | Python 规则引擎 + 仲裁器 | 强制执行 |
| **记忆层** | Mindol 语义记忆 | 跨会话持久 |
| **钩子层** | 5 个 Codex 生命周期钩子 | 全域常驻 |
| **分发层** | plugin.json | Codex 插件包装 |
| **文档层** | SKILL.md | 让 Codex 理解自己正在运行什么 |

### 与纯技能的根本区别
| 维度 | 纯技能 | 迭进 |
|:---|:---:|:---:|
| 生效方式 | 模型主动读取后生效 | hooks 自动注入执行 |
| 约束力 | 建议性 | 强制性（规则引擎裁决，exit code 阻断） |
| 常驻能力 | 无，不加载就不存在 | 有，每次工具调用前自动拦截 |
| 记忆 | 无，依赖当前上下文 | 有，Mindol + SQLite，跨会话持久 |
| 自我迭代 | 不能 | 能（一二不过三 → 规则进化 → 自动升级） |

---

## ⚡迭进协议 DGEN-000（机械执行 · 不可绕过）



### 协议 A：状态显示（每次回复可选尾部摘要）

每次回复前，按序执行：

1. 读取 {CODEX_HOME}/diegin/var/state/dgen_status.txt

2. 解析 STATUS / RULES / DECISION / MATCHED 字段

3. 在回复**正文开头**输出：

   ⚡ DGEN STATUS: {STATUS} | {RULES} 规则 | {DECISION}

   例如：⚡ DGEN STATUS: ACTIVE | 14 规则 | allow

4. 如果文件不存在或读取失败，输出：

   ⚡ DGEN STATUS: BOOT | ? 规则 | init



### 协议 B：引擎预检（自动执行，无需标记）

- 每次触发 PreToolUse 时，自动执行 python call_diegin.py check 引擎预检
- 无需在工具命令中嵌入 [DGEN STATUS:] 标记
- 引擎裁决通过 exit code 传递：0=放行，靐0=阻断（含原因说明）
- 一二不过三第3次升级后自动切换执行模式（enforce→audit）



### 协议 C：跨回合续签

- 引擎预检按需执行，无需在工具命令中嵌入标记
- 如长时间无交互（>5分钟），引擎自动重置检查状态
- 阻断/升级时用户会收到通知

- 如长时间无交互（>5分钟），标记自动过期 → 需重新 [DGEN STATUS:]


## ⚡迭进强制规则（机械执行 · 不可绕过）



### 规则 0：[DGEN] 状态摘要（尾部可选）

每次回复末尾可附带迭进状态摘要（可选，不影响正文阅读）：

- ✅ [DGEN] 通过 | 规则: <规则ID> | 策略: <策略名>
- 🛑 [DGEN] 拦截 X 条 | 裁决: block | 规则: <规则ID>


- [DGEN] ⚠️ 重新激活



**违反后果：** 迭进引擎标记未激活，后续操作将被自动拦截。



### 规则 0-1：工具调用前自动预检

每次调用工具前，PreToolUse 钩子自动执行引擎预检。
无需手动确认 [DGEN] 状态，钩子自动处理。




**违反后果：** 迭进引擎标记未激活，后续操作将被自动拦截。


## 一、八元原则网络（迭进元原则·全域不可绕过）

八个元原则以网络而非线性方式运作，各有职责、触发时机和闭环出口，通过**裁决律**和**去伪存真**互联。

每条原则的完整定义（步序、时机、闭环、互联、约束）见 `references/principles.md`，此处仅列概要：

| # | 原则 | 方向 | 一句话 |
|:--|:----|:----|:-------|
| 0 | **裁决律** | 仲裁 | P0-P5 硬编码优先级，真伪至上 → 生存优先 → 完形封存 |
| 1 | **守三** | 防守 | 拆解自己 → 找出不足 → 对比提练 → 总结改进 → 写入固化 |
| 2 | **攻七** | 进攻 | 识别优势 → 复盘成功 → 提炼模式 → 主动写入 → 验证效果 |
| 3 | **一二不过三** | 安全阀 | 错立改+改毕验 → 再错加固阻断 → 三错升级处理 |
| 4 | **举一反三** | 扩展 | 举一 → 反三 → 通百 → 回归校验 |
| 5 | **去伪存真** | 硬地板 | 言必有证 → 证必可验 → 验证为真 |
| 6 | **缓急律** | 节奏 | 急务求效 → 缓务求真 → 张弛有度 |
| 7 | **止观门** | 封存 | 事毕封存 → 投入清零 → 不恋战，不内耗 |

### 网络总览（执行流）

```
入口：[缓急律] 判断任务类型 → 紧急走快速通道，常规走完整流程
  ↓
[去伪存真] 验证输入信息真实性
  ↓
[守三·轻量] 扫描最近一次失败模式
  ↓
执行操作
 ↙            ↘
成功           失败
 ↓              ↓
[攻七]          [一二不过三]
 识别→提炼      立改+改毕验
 →写入→验证      →第2次→归因过滤→写入硬阻断
  ↓              →第3次→升级处理
[举一反三]        ↓
 从新模式推导    [去伪存真]回归校验
 →staging        ↓
[去伪存真]       [仲裁器·裁决律]
 回归校验        按优先级裁决
  ↓              ↓
[仲裁器·裁决律]  [止观门]封存本轮
 ↓              [守三·深度]离线复盘
[止观门]封存本轮
[守三·深度]离线复盘
```

*完整描述（步序/时机/闭环/互联/约束表）见 `references/principles.md`。*

## 二、执行流程（全域常驻）



每次 AI 回复前，八元原则网络按以下顺序执行：



```

用户消息/事件

  → [缓急律] 判断任务类型 ─── 紧急? → 守三(轻量)→执行→止观门(简版)

  │                         └── 常规? → 完整流程↓

  → [去伪存真] 验证输入信息真实性

  → [守三·轻量] 扫描最近一次失败模式

  → 执行操作（工具调用/回复生成）

  ├── 成功 → [攻七] 识别优势→提炼模式→写入→调用去伪存真验证

  │          → [举一反三] 从新模式推导跨场景候选→staging

  │          → [去伪存真] 回归校验staging规则

  └── 失败 → [一二不过三] 检测错误→立改+改毕验

             → 修复成功? → 输出到攻七

             → 第2次? → 归因过滤→内生惯性→写入硬阻断

             → 第3次? → 升级处理

  → [仲裁器·裁决律] 汇集所有原则输出→按优先级裁决

  → [止观门] 封存本轮→清除工作内存

  → [守三·深度] 每日/每N次→收集数据→拆解→总结→写入固化→下一轮

  → [DGEN] 输出裁决结果

```



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



## 五、指令



| 指令 | 效果 |

|:---|:---:|

| 接入迭进 / dgen on | 加载系统规则 + 当前场景领域规则 |

| @迭进 | 立即触发迭进引擎预检，输出原始 JSON |

| 迭进状态 | 规则库 / 置信度 / 健康度报告 |

| 守三攻七复盘 | 负向纠错 + 正向强化 |

| dgen feedback <ID> <agree/veto/silent> | 对规则给出反馈，引擎自动调整置信度 |

| dgen domain list | 列出所有领域规则包 |

| dgen domain activate <domain> | 激活指定领域 |



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



## 七、Mindol 语义记忆引擎



Mindol 是迭进的**权威语义记忆引擎**，零外部依赖，纯本地运行。



### 架构



`

Mindol（内存优先·权威存储） ↔ RuleEngine（规则引擎）

├─ rule      202 条规则（语义可检索）        JSON 副本（人类可读）

├─ pattern    6 条成功模式

├─ trade      2 条 strike + 30 条 Relation   hooks → mindol_bridge

├─ state      1 条阶段状态                     pre_check 上下文注入

└─ codex    582 条决策归档                     post_review 自动归档

`



### 性能



| 对比项 | Mindol | 传统 embedding |

|:---|:---:|:---:|

| 向量化 | SHA256 n-gram hash（~0.01ms） | OpenAI API（50-200ms） |

| 检索 | 内存 numpy dot product（~2ms） | 网络查询 |

| 外部依赖 | 零 | OpenAI Key |

| 可离线 | ✅ | ❌ |



### 权威转换



`

写入: API → Mindol(ACID事务) → JSON(人类可读副本)

读取: Mindol(权威) → 失败时回退 JSON → 失败时种子注入

恢复: Mindol↔JSON 互为备份，双向重建

`



### 方式 A：纯 Markdown（零依赖 · 所有 Agent 通用）



让 AI 读取本 SKILL.md，即可在回复中执行迭进预检。



### 方式 B：Python 引擎



ash

cd engine && uv run python call_diegin.py activate





### 方式 C：自动化引擎



ash

python scripts/dgen_evolve.py   # 初始化健康度基线




## 八、Hooks 机制（Codex 事件驱动·全域常驻）



| Hook | 触发时机 | Mindol 写入 | AI 回馈 |

|:---|:---|:---:|:---:|

| SessionStart | 会话启动 | ✅ 初始化 | - |

| PreToolUse | 工具调用前 | ✅ mindol_bridge | ✅ display_line 阻断 |

| UserPromptSubmit | 用户消息 | ✅ mindol_bridge | ✅ mindol_context + diegin_context.json |

| PostToolUse | 工具调用后 | ✅ mindol_bridge | ✅ post_review 归档 |

| SessionStop | 会话停止 | ✅ mindol_bridge | ✅ 硬地板检查 |



### 回馈数据流



`

pre_check() → mindol_context + display_line

     → diegin_context.json（AI 可读取的结构化上下文）

     → Write-Output（hook 标准输出 → Codex 裁决引擎）

     → memory_archive()（Mindol codex 空间归档）

`


## 九、跨场景接入规则



| 场景 | 要求 |

|:---|:---:|

| 用户直接回复 | **必须**迭进预检 |

| 定时任务输出 | **必须**迭进预检 |

| 跨会话消息 | **必须**迭进预检 |

| 纯工具调用（无回复） | 不需要 |

| 回复无 [DGEN] 标记 | 立即重新激活，标注 ⚠️ 重新激活 |



---



## 十、安全阀



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












