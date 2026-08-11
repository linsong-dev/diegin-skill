<p align="center">
  <img src="assets/logo.svg" width="200" alt="DGEN">
</p>

<h1 align="center">迭进 · DGEN</h1>

<p align="center">
  <b>AI 全域常驻自我迭代进化系统</b><br>
  让 AI 像人一样从错误中学习，越用越聪明
</p>

<p align="center">
  [![EN](https://img.shields.io/badge/EN-README-blue)](README.en.md) | [![中文](https://img.shields.io/badge/中文-README-red)](README.md) | <a href="https://github.com/linsong-dev/diegin-skill/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License">
  </a>
  <img src="https://img.shields.io/badge/version-3.8.1-brightgreen" alt="Version">
  <img src="https://img.shields.io/badge/python-3.12+-orange" alt="Python">
  <img src="https://img.shields.io/badge/Codex-ready-purple" alt="Codex">
</p>

---

## 30 秒看懂迭进

迭进是一个 **AI 操作系统级进化层**。不调任何外部 API，不依赖 GPU，纯 Python 运行。

> 普通 AI：犯过的错下次还可能再犯
>
> 带迭进的 AI：错误自动检测 → 立改加固 → 举一反三 → 不再重犯

## 架构

`
用户操作 → [缓急律] 判断任务类型
         → [去伪存真] 验证信息真实性
         → [守三·轻量] 扫描失败模式
         → 执行操作
            ├─ 成功 → [攻七] 提炼成功模式
            └─ 失败 → [一二不过三] 立改→加固→升级
         → [仲裁器·裁决律] 按优先级裁决
         → [止观门] 封存本轮
         → [守三·深度] 离线复盘
`

## 核心文件

| 文件 | 作用 |
|:-----|:------|
| engine/evo/main.py | 统一入口 + 定期维护 |
| engine/evo/rule_engine.py | 规则引擎（235 条规则（active 42），CRUD + 匹配 + RULE-GUARD 触发写入门） |
| engine/evo/tracker.py | 行为追踪（一二不过三连锁、守三攻七循环） |
| engine/evo/arbiter.py | 仲裁器（P0-P5 优先级裁决） |
| engine/evo/pacemaker.py | 缓急律调度（宕机时段） |
| engine/evo/closure.py | 止观门（认知封存） |
| engine/evo/evidence_vault.py | 去伪存真证据库 + 季度证伪 |
| engine/evo/error_detector.py | 错误检测 + 一二不过三阻断 |
| engine/evo/dashboard.py | 健康度仪表盘 |
| engine/mindol/ | Mindol 语义记忆引擎 |
| references/whitepaper.md | AI 自我进化系统白皮书 v1.0（八元原则方法论） |

## 八元原则

| # | 原则 | 方向 | 机制 |
|:-:|:----|:---:|:-----|
| 1 | 攻七 | 进攻 | 识长处 → 炼精华 → 固其用（v3.8：优先复用验证过的正确做法） |
| 2 | 守三 | 防守 | 观不足 → 省其因 → 正其行 |
| 3 | 一二不过三 | 安全阀 | 立改 → 加固 → 升级（三错封顶）|
| 4 | 举一反三 | 扩展 | 举一 → 反三 → 通百 → 回归校验 |
| 5 | 去伪存真 | 硬地板 | 言必有证 → 证必可验 → 验证为真 + 季度证伪 |
| 6 | 裁决律 | 宪法 | 真伪至上 → 生存优先 → 完形封存 |
| 7 | 缓急律 | 节奏 | 急务求效 → 缓务求真 → 张弛有度 |
| 8 | 止观门 | 封存 | 事毕封存 → 投入清零 → 不恋战 |

> **编号为认知顺序；执行优先级以裁决律 P0-P5 为准，不受编号顺序影响。**

**运行时主导映射：**

| 裁决律分级 | 运行时主导原则 |
|:---|:---|
| P0 真伪 | 去伪存真（假信息不入任何流程） |
| P1 安全 | 一二不过三（阻断优先于强化/泛化） |
| P2 完形 | 止观门（事毕清零，不追加纠错） |
| P3 紧急 | 缓急律（紧急直通，不启动深度复盘） |
| P4 置信 | 攻七 / 守三（置信度高者胜出） |
| P5 staging | 举一反三（先经去伪存真验证再激活） |

> **认知顺序用于学习与叙事；运行时主导权由裁决律 P0-P5 决定。两个维度不同，互不冲突。**

## 攻七强化（v3.8）

验证过的正确做法 → **及时推荐 → 优先选用 → 快速泛化 → 采纳反馈**：

- **及时使用**：`pre_check` 高置信度模式标 priority，工具调用前直接推荐采用
- **优先选用**：仲裁器 P4 同场景加权 +0.5（同工具复用验证过的方法优先于负向纠错）
- **泛化提速**：复用≥2 次或 conf≥4.5 即触发跨域泛化
- **反馈闭环**：工具成功自动采纳（置信度+0.5）；否决 ×0.7
- **质量护栏**：`audit_patterns` / `audit_staging` / `audit_evidence` 防空壳与假数据再生

## 实战案例（2026-08-10 实测）

- **举一反三 ×2 当日 71/74 次命中、零误伤**：08-09 入库的 2 条跨域泛化规则（`pat_rule_pat_manual_ps1_chinese_bom` / `pat_rule_pat_manual_backup_before_remove`）08-10 即在实战中触发 71/74 次，人工复核 boundary 明确、无误伤，按裁决保留并正式发布。
- **image_url 守三 11 次审计**：同一会话内 view_image 连发触发「一二不过三」，`self_error_image_url` 从 archived 升级 critical 复活，当日 11 次命中全部走 audit（熔断期行为），按计划 ≈08-17 复查，无复发可人工 reset。
- **乱码根因修复**：PS5.1 ↔ Python 管道中文乱码（`$OutputEncoding` 默认 US-ASCII、`[Console]::OutputEncoding` 默认 GBK）导致 prompt 入库变 `?`、pre_reply JSON 解析失败 → 强制 UTF-8 + 质量门正则惰性量词修复；7 个被拒的攻七模式恢复提升，经验沉淀管线卡死闭环。
- **攻七规则当日 auto_adopt**：08-09 入库的攻七规则（`pat_manual_doc_writeback_verify` ×4、`pat_manual_new_tool_smoke` ×1）08-10 实战当日自动采纳（置信度 +0.5），「入库 → 实战 → 采纳」闭环 24 小时内跑通。

## 快速开始
### 环境要求
- Python 3.12+
- Codex 桌面版（v3.0+，26.x 已内置迭进钩子支持）
- PowerShell 5.1+

### 安装
`powershell
git clone https://github.com/linsong-dev/diegin-skill.git
cd Diegin
pip install numpy
`

### 注册钩子
将 config/hooks.json 中 %CODEX_HOME% 替换为你的 Codex 安装路径，合并到 %CODEX_HOME%/hooks.json，重启 Codex。

### 激活
在 Codex 对话中输入 接入迭进 或 dgen on。

### 验证
`powershell
cd engine
python test_all.py --verbose
`
预期输出：结果: 32/32 通过 (0 失败)

## 快速使用

| 命令 | 效果 |
|:-----|:------|
| 接入迭进 或 dgen on | 激活迭进引擎 |
| 迭进状态 | 查看规则库 / 置信度 / 健康度 |
| 守三攻七复盘 | 负向纠错 + 正向强化 |
| @迭进 | 触发预检，输出原始 JSON |
| dgen feedback <ID> <agree/veto/silent> | 对规则反馈，调整置信度 |

## 配置

`	oml
[pacemaker]
downtime_start = "23:00"
downtime_end   = "06:00"

[evidence_vault]
quarterly_falsification_enabled = true
`

## 项目结构

`
diegin/
├── engine/           Python 引擎
│   ├── call_diegin.py    CLI 入口
│   ├── test_all.py       32 个端到端测试
│   ├── evo/              八元原则引擎
│   └── mindol/           Mindol 语义记忆引擎
├── hooks/             PowerShell 钩子（全域常驻）
├── config/            路由配置
├── assets/            Logo 等资源
├── tests/             测试套件
├── sync.ps1           同步脚本
├── deploy/            部署脚本
└── LICENSE            Apache 2.0
